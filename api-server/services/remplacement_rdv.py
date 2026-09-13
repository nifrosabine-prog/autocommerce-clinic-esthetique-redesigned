"""Suggestions de remplacement après annulation, sans réservation automatique."""
from datetime import timedelta
from sqlalchemy import or_, select
from models.database import RendezVous, StatutRDV, SuggestionRemplacementRdv


async def proposer_creneaux_apres_annulation(db, rdv: RendezVous, *, clinic_id: int, limit: int = 3):
    duration = (rdv.date_heure_fin - rdv.date_heure_debut) if rdv.date_heure_fin else timedelta(minutes=30)
    suggestions = []
    for weeks in (1, 2, 3, 4):
        start = rdv.date_heure_debut + timedelta(weeks=weeks)
        end = start + duration
        conflict = await db.scalar(select(RendezVous.id).where(
            RendezVous.clinic_id == clinic_id,
            RendezVous.praticien_id == rdv.praticien_id,
            RendezVous.statut.notin_([StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value]),
            RendezVous.date_heure_debut < end,
            or_(RendezVous.date_heure_fin.is_(None), RendezVous.date_heure_fin > start),
        ).limit(1))
        if conflict is not None:
            continue
        item = SuggestionRemplacementRdv(
            clinic_id=clinic_id, rdv_annule_id=rdv.id, praticien_id=rdv.praticien_id,
            date_heure_debut=start, date_heure_fin=end, statut="a_valider",
        )
        db.add(item)
        suggestions.append(item)
        if len(suggestions) >= limit:
            break
    await db.flush()
    return suggestions


async def valider_suggestion(db, suggestion_id: int, *, clinic_id: int, validated_by: int):
    suggestion = await db.scalar(select(SuggestionRemplacementRdv).where(
        SuggestionRemplacementRdv.id == suggestion_id,
        SuggestionRemplacementRdv.clinic_id == clinic_id,
        SuggestionRemplacementRdv.statut == "a_valider",
    ))
    if not suggestion:
        raise ValueError("Suggestion introuvable ou déjà traitée")
    original = await db.scalar(select(RendezVous).where(
        RendezVous.id == suggestion.rdv_annule_id, RendezVous.clinic_id == clinic_id
    ))
    if not original or original.statut != StatutRDV.ANNULE.value:
        raise ValueError("Le rendez-vous initial n'est plus annulé")
    conflict = await db.scalar(select(RendezVous.id).where(
        RendezVous.clinic_id == clinic_id, RendezVous.praticien_id == suggestion.praticien_id,
        RendezVous.statut.notin_([StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value]),
        RendezVous.date_heure_debut < suggestion.date_heure_fin,
        or_(RendezVous.date_heure_fin.is_(None), RendezVous.date_heure_fin > suggestion.date_heure_debut),
    ).limit(1))
    if conflict:
        raise ValueError("Le créneau n'est plus disponible")
    replacement = RendezVous(
        clinic_id=clinic_id, patient_id=original.patient_id, praticien_id=suggestion.praticien_id,
        acte_id=original.acte_id, date_heure_debut=suggestion.date_heure_debut,
        date_heure_fin=suggestion.date_heure_fin, salle=original.salle,
        statut=StatutRDV.PLANIFIE.value, source="remplacement", remplace_rdv_id=original.id,
        created_by=validated_by,
    )
    db.add(replacement)
    await db.flush()
    suggestion.statut = "validee"
    suggestion.valide_par = validated_by
    suggestion.nouveau_rdv_id = replacement.id
    await db.flush()
    return replacement


async def suggerer_cascade_apres_refus(db, rdv_decline: RendezVous, *, clinic_id: int):
    """Bloc 3 — cascade d'annulation.

    Un patient a répondu ``NON`` au rappel J-1 : on ne touche jamais au RDV
    (aucune annulation ni réaffectation automatique — décision et action
    restent entièrement à l'équipe, conformément aux règles dures de Lina).
    On se contente de chercher, à titre de suggestion, un autre patient
    ayant un rendez-vous plus tardif avec le même praticien qui pourrait
    être avancé sur ce créneau désormais probablement libre, et on dépose
    une tâche interne pour que l'assistante décide et agisse elle-même.
    """
    from models.database import Patient
    from models.security import TacheInterneAssistant

    candidate_rdv = await db.scalar(
        select(RendezVous)
        .where(
            RendezVous.clinic_id == clinic_id,
            RendezVous.praticien_id == rdv_decline.praticien_id,
            RendezVous.patient_id != rdv_decline.patient_id,
            RendezVous.statut.in_([StatutRDV.PLANIFIE.value, StatutRDV.CONFIRME.value]),
            RendezVous.date_heure_debut > rdv_decline.date_heure_debut,
            RendezVous.date_heure_debut <= rdv_decline.date_heure_debut + timedelta(days=7),
        )
        .order_by(RendezVous.date_heure_debut.asc())
        .limit(1)
    )
    if candidate_rdv is None:
        return None

    declining_patient = await db.get(Patient, rdv_decline.patient_id)
    candidate_patient = await db.get(Patient, candidate_rdv.patient_id)
    titre = (
        f"{declining_patient.prenom if declining_patient else 'Un patient'} a décliné son RDV du "
        f"{rdv_decline.date_heure_debut.strftime('%d/%m à %H:%M')} — "
        f"{candidate_patient.prenom if candidate_patient else 'un autre patient'} a RDV le "
        f"{candidate_rdv.date_heure_debut.strftime('%d/%m à %H:%M')}, le contacter pour lui proposer ce créneau ?"
    )
    task = TacheInterneAssistant(
        clinic_id=clinic_id,
        patient_id=candidate_rdv.patient_id,
        titre=titre[:255],
        description=(
            f"RDV décliné #{rdv_decline.id} (patient #{rdv_decline.patient_id}) — "
            f"RDV candidat à avancer #{candidate_rdv.id} (patient #{candidate_rdv.patient_id})."
        ),
        priorite="normale",
    )
    db.add(task)
    await db.flush()
    return task
