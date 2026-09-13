"""
AutoCommerce Clinic — Bloc 3 : parcours d'arrivée du patient.

Relie l'agenda, les réservations (Internet / WhatsApp / téléphone / manuel),
le CRM (prospects) et l'épisode patient pendant l'arrivée :

  réservation → doublons → RDV → arrivée → présence confirmée → accord
  d'examen → ouverture de l'épisode ; absence → historique conservé ;
  remplacement → NOUVEAU RDV sans écraser l'ancien.

Règles imposées par le cahier des charges Bloc 3 :
  - Ne jamais supprimer un ancien rendez-vous.
  - Toute modification importante journalise un événement d'agenda avec
    ancienne valeur, nouvelle valeur, auteur, date et motif (table
    rdv_evenements).
  - À chaque création / modification : mise à jour du CRM (prospect),
    timeline du patient (événements), épisode patient (ouverture à l'accord),
    tâche de l'assistante.
  - Un RDV Internet et un RDV WhatsApp suivent exactement le même modèle
    qu'un RDV manuel : seule la valeur `source` diffère.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import (
    RendezVous, Patient, Utilisateur, ActeMedical, DossierMedical, StatutRDV, RoleEnum,
)
from models.episode_core import (
    Prospect, StatutProspect, EpisodePatient, StatutEpisode, RdvEvenement,
)
from models.security import TacheInterneAssistant, StatutTacheInterneEnum
from services.agenda import creer_rdv
from services.dossier_medical import create_dossier

SOURCES_RESERVATION = {"internet", "whatsapp", "telephone", "manuel"}
EVENEMENT_CREATION = "creation"
EVENEMENT_ARRIVEE = "arrivee"
EVENEMENT_PRESENCE = "presence_confirmee"
EVENEMENT_ACCORD = "accord_examen"
EVENEMENT_ABSENCE = "absence"
EVENEMENT_REMPLACEMENT = "remplacement"
EVENEMENT_ANNULATION = "annulation"
EVENEMENT_REPORT = "report"
EVENEMENT_STATUT = "modification_statut"


# ── Journalisation des événements d'agenda ──────────────────

def snapshot_rdv(rdv: RendezVous) -> dict:
    """Instantané JSON des champs métier du rendez-vous."""
    return {
        "statut": rdv.statut,
        "date_heure_debut": rdv.date_heure_debut.isoformat() if rdv.date_heure_debut else None,
        "date_heure_fin": rdv.date_heure_fin.isoformat() if rdv.date_heure_fin else None,
        "praticien_id": rdv.praticien_id,
        "acte_id": rdv.acte_id,
        "salle": rdv.salle,
        "source": rdv.source,
        "reference": rdv.reference,
        "remplace_rdv_id": rdv.remplace_rdv_id,
    }


def generer_reference(rdv: RendezVous) -> str:
    """Référence stable exploitable par la recherche (ex. RDV1-000123)."""
    return f"RDV{rdv.clinic_id}-{rdv.id:06d}"


async def journaliser_evenement(
    db: AsyncSession,
    *,
    rdv: RendezVous,
    type_evenement: str,
    ancienne: dict,
    nouvelle: dict,
    auteur_id: Optional[int],
    motif: Optional[str] = None,
) -> RdvEvenement:
    """Enregistre un événement d'agenda (critère Bloc 3 : ancienne valeur,
    nouvelle valeur, auteur, date et motif)."""
    import json

    evenement = RdvEvenement(
        clinic_id=rdv.clinic_id,
        rdv_id=rdv.id,
        patient_id=rdv.patient_id,
        type_evenement=type_evenement,
        ancienne_valeur=json.dumps(ancienne, ensure_ascii=False, default=str),
        nouvelle_valeur=json.dumps(nouvelle, ensure_ascii=False, default=str),
        auteur_id=auteur_id,
        motif=motif,
        cree_le=datetime.utcnow(),
    )
    db.add(evenement)
    await db.flush()
    await db.commit()
    return evenement


async def evenements_rdv(db: AsyncSession, rdv_id: int, clinic_id: int) -> list[dict]:
    """Historique complet et ordonné d'un rendez-vous."""
    result = await db.execute(
        select(RdvEvenement)
        .where(RdvEvenement.rdv_id == rdv_id, RdvEvenement.clinic_id == clinic_id)
        .order_by(RdvEvenement.cree_le.asc(), RdvEvenement.id.asc())
    )
    retour = []
    for ev in result.scalars().all():
        retour.append({
            "id": ev.id,
            "type_evenement": ev.type_evenement,
            "ancienne_valeur": ev.ancienne_valeur,
            "nouvelle_valeur": ev.nouvelle_valeur,
            "auteur_id": ev.auteur_id,
            "motif": ev.motif,
            "cree_le": ev.cree_le.isoformat() if ev.cree_le else None,
        })
    return retour


# ── Tâche d'accueil pour l'assistante ───────────────────────

async def creer_tache_accueil(
    db: AsyncSession,
    *,
    rdv: RendezVous,
    patient: Patient,
    auteur_id: int,
) -> TacheInterneAssistant:
    titre = f"Accueil patient {patient.prenom} {patient.nom}"
    description = (
        f"RDV {rdv.reference or rdv.id} — {rdv.date_heure_debut.strftime('%d/%m/%Y à %Hh%M')}"
        f"{', salle ' + rdv.salle if rdv.salle else ''} — source {rdv.source or 'manuel'}"
    )
    tache = TacheInterneAssistant(
        clinic_id=rdv.clinic_id,
        creee_par_id=auteur_id,
        assignee_id=auteur_id,
        patient_id=patient.id,
        titre=titre,
        description=description,
        priorite="normale",
        statut=StatutTacheInterneEnum.A_FAIRE.value,
        due_at=rdv.date_heure_debut,
    )
    db.add(tache)
    await db.flush()
    return tache


# ── CRM : prospects (pré-patient unifié) ─────────────────────

async def upsert_prospect_crm(
    db: AsyncSession,
    *,
    clinic_id: int,
    nom: str,
    prenom: str,
    telephone: str,
    email: Optional[str],
    source: str,
    patient_id: Optional[int] = None,
) -> tuple[Prospect, bool]:
    """Retrouve ou crée le prospect (doublon par téléphone) et le relie au
    patient existant le cas échéant. Retourne (prospect, cree)."""
    result = await db.execute(
        select(Prospect).where(
            Prospect.clinic_id == clinic_id,
            Prospect.telephone == telephone,
        ).order_by(Prospect.id.desc())
    )
    prospect = result.scalars().first()
    if prospect is not None:
        if patient_id is not None and not prospect.patient_id:
            prospect.patient_id = patient_id
            prospect.statut = StatutProspect.QUALIFIE.value
        if not prospect.source or prospect.source == "inconnue":
            prospect.source = source
        prospect.prenom = prenom or prospect.prenom
        if email and not prospect.email:
            prospect.email = email
        await db.flush()
        return prospect, False

    prospect = Prospect(
        clinic_id=clinic_id,
        nom=nom,
        prenom=prenom,
        telephone=telephone,
        email=email,
        source=source,
        statut=StatutProspect.QUALIFIE.value if patient_id else StatutProspect.NOUVEAU.value,
        patient_id=patient_id,
    )
    db.add(prospect)
    await db.flush()
    return prospect, True


async def rechercher_doublons(
    db: AsyncSession,
    *,
    clinic_id: int,
    telephone: Optional[str] = None,
    nom: Optional[str] = None,
    prenom: Optional[str] = None,
    email: Optional[str] = None,
) -> dict:
    """Détection de doublons patient/prospect avant création (Bloc 3)."""
    doublons_patients: list[dict] = []
    doublons_prospects: list[dict] = []

    if telephone:
        result = await db.execute(
            select(Patient).where(Patient.clinic_id == clinic_id, Patient.telephone == telephone)
        )
        doublons_patients += [
            {"id": p.id, "nom": p.nom, "prenom": p.prenom, "telephone": p.telephone, "email": p.email}
            for p in result.scalars().all()
        ]
        result = await db.execute(
            select(Prospect).where(Prospect.clinic_id == clinic_id, Prospect.telephone == telephone)
        )
        doublons_prospects += [
            {"id": p.id, "nom": p.nom, "prenom": p.prenom, "telephone": p.telephone, "statut": p.statut}
            for p in result.scalars().all()
        ]

    if nom and prenom:
        mineur = f"%{nom.strip().lower()}%"
        majeur = f"%{prenom.strip().lower()}%"
        result = await db.execute(
            select(Patient).where(
                Patient.clinic_id == clinic_id,
                or_(
                    Patient.nom.ilike(mineur),
                    Patient.prenom.ilike(majeur),
                ),
            )
        )
        ids_deja = {p["id"] for p in doublons_patients}
        doublons_patients += [
            {"id": p.id, "nom": p.nom, "prenom": p.prenom, "telephone": p.telephone, "email": p.email}
            for p in result.scalars().all() if p.id not in ids_deja
        ]

    if email:
        result = await db.execute(
            select(Patient).where(Patient.clinic_id == clinic_id, Patient.email == email)
        )
        ids_deja = {p["id"] for p in doublons_patients}
        doublons_patients += [
            {"id": p.id, "nom": p.nom, "prenom": p.prenom, "telephone": p.telephone, "email": p.email}
            for p in result.scalars().all() if p.id not in ids_deja
        ]

    return {"patients": doublons_patients, "prospects": doublons_prospects}


async def trouver_patient_par_telephone(db: AsyncSession, *, clinic_id: int, telephone: str) -> Optional[Patient]:
    result = await db.execute(
        select(Patient).where(Patient.clinic_id == clinic_id, Patient.telephone == telephone)
    )
    return result.scalars().first()


async def creer_patient_simple(
    db: AsyncSession,
    *,
    clinic_id: int,
    nom: str,
    prenom: str,
    telephone: str,
    email: Optional[str] = None,
    source: str = "manuel",
) -> Patient:
    patient = Patient(
        clinic_id=clinic_id,
        nom=nom,
        prenom=prenom,
        telephone=telephone,
        email=email,
        source_acquisition=source,
    )
    db.add(patient)
    await db.flush()
    return patient


# ── Création unifiée d'une réservation (Internet/WhatsApp/tél./manuel) ──

async def creer_rdv_complet(
    db: AsyncSession,
    current_user: dict,
    *,
    source: str,
    nom: str,
    prenom: str,
    telephone: str,
    acte_id: int,
    praticien_id: int,
    date_heure: datetime,
    email: Optional[str] = None,
    salle: Optional[str] = None,
    patient_id: Optional[int] = None,
    motif: Optional[str] = None,
) -> dict:
    """Point d'entrée unique du parcours d'arrivée.

    Le flux est identique quelle que soit la source (internet, whatsapp,
    telephone, manuel) : doublons → patient (existant ou créé) → prospect CRM
    → RDV → événement de création → tâche de l'assistante."""
    clinic_id = int(current_user["clinic_id"])
    auteur_id = int(current_user["id"])

    if source not in SOURCES_RESERVATION:
        raise ValueError(f"Source de réservation inconnue : {source}")
    if not nom.strip() or not prenom.strip() or not telephone.strip():
        raise ValueError("Nom, prénom et téléphone obligatoires")
    if isinstance(date_heure, str):
        date_heure = datetime.fromisoformat(date_heure)

    patient = None
    doublons = await rechercher_doublons(
        db, clinic_id=clinic_id,
        telephone=telephone, nom=nom, prenom=prenom, email=email,
    )
    if patient_id is not None:
        result = await db.execute(
            select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
        )
        patient = result.scalar_one_or_none()
        if patient is None:
            raise ValueError("Patient introuvable dans cette clinique")
    else:
        patient = await trouver_patient_par_telephone(db, clinic_id=clinic_id, telephone=telephone)
        if patient is None:
            patient = await creer_patient_simple(
                db, clinic_id=clinic_id,
                nom=nom.strip(), prenom=prenom.strip(),
                telephone=telephone.strip(), email=email, source=source,
            )
        else:
            if email and not patient.email:
                patient.email = email
            await db.flush()

    prospect, _ = await upsert_prospect_crm(
        db, clinic_id=clinic_id, nom=patient.nom, prenom=patient.prenom,
        telephone=patient.telephone, email=patient.email or email,
        source=source, patient_id=patient.id,
    )

    rdv, _ = await creer_rdv(
        patient_id=patient.id,
        praticien_id=praticien_id,
        acte_id=acte_id,
        date_heure=date_heure,
        salle=salle,
        db=db,
        created_by=auteur_id,
        clinic_id=clinic_id,
    )
    rdv.source = source
    rdv.reference = generer_reference(rdv)
    await db.flush()
    await db.commit()

    await journaliser_evenement(
        db, rdv=rdv, type_evenement=EVENEMENT_CREATION,
        ancienne={}, nouvelle=snapshot_rdv(rdv),
        auteur_id=auteur_id, motif=motif or f"Réservation via {source}",
    )
    tache = await creer_tache_accueil(db, rdv=rdv, patient=patient, auteur_id=auteur_id)

    return {
        "rdv_id": rdv.id,
        "reference": rdv.reference,
        "statut": rdv.statut,
        "source": rdv.source,
        "patient_id": patient.id,
        "prospect_id": prospect.id,
        "doublons_detectes": bool(doublons["patients"] or doublons["prospects"]),
        "tache_id": tache.id,
    }


# ── Flux d'arrivée ──────────────────────────────────────────

async def _charger_rdv(db: AsyncSession, rdv_id: int, clinic_id: int) -> RendezVous:
    result = await db.execute(
        select(RendezVous).where(RendezVous.id == rdv_id, RendezVous.clinic_id == clinic_id)
    )
    rdv = result.scalar_one_or_none()
    if rdv is None:
        raise ValueError("Rendez-vous introuvable dans cette clinique")
    return rdv


async def confirmer_arrivee(db: AsyncSession, current_user: dict, rdv_id: int) -> dict:
    """Patient arrivé à l'accueil ; prépare l'épisode sans valoir consentement."""
    rdv = await _charger_rdv(db, rdv_id, int(current_user["clinic_id"]))
    if rdv.statut in (StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value, StatutRDV.TERMINE.value):
        raise ValueError(f"Impossible : rendez-vous au statut {rdv.statut}")
    ancien = snapshot_rdv(rdv)
    rdv.statut = StatutRDV.ARRIVE.value
    await db.flush()
    episode_result = await db.execute(
        select(EpisodePatient).where(
            EpisodePatient.patient_id == rdv.patient_id,
            EpisodePatient.clinic_id == int(current_user["clinic_id"]),
            EpisodePatient.statut.notin_([StatutEpisode.CLOTURE.value, StatutEpisode.ANNULE.value]),
        ).order_by(EpisodePatient.id.desc())
    )
    episode = episode_result.scalars().first()
    if episode is None:
        episode = EpisodePatient(
            clinic_id=int(current_user["clinic_id"]), patient_id=rdv.patient_id,
            rdv_origine_id=rdv.id, statut=StatutEpisode.OUVERT.value,
            ouvert_par_id=int(current_user["id"]),
        )
        db.add(episode)
        await db.flush()

    # Le dossier médical partagé est le support clinique de l'épisode. Il
    # doit exister dès l'arrivée pour que l'accueil et les professionnels
    # puissent travailler sur le même dossier, même avant le consentement et
    # la saisie médicale complète. `draft=True` conserve cette séparation :
    # l'arrivée ne clôture pas le dossier et ne vaut jamais consentement.
    dossier = await db.scalar(
        select(DossierMedical).where(
            DossierMedical.clinic_id == int(current_user["clinic_id"]),
            DossierMedical.patient_id == rdv.patient_id,
            DossierMedical.episode_id == episode.id,
        ).order_by(DossierMedical.id.desc()).limit(1)
    )
    if dossier is None:
        dossier = await create_dossier(
            patient_id=rdv.patient_id,
            praticien_id=rdv.praticien_id,
            rdv_id=rdv.id,
            data={"acte_id": rdv.acte_id, "episode_id": episode.id},
            db=db,
            clinic_id=int(current_user["clinic_id"]),
            draft=True,
        )
    await journaliser_evenement(
        db, rdv=rdv, type_evenement=EVENEMENT_ARRIVEE,
        ancienne=ancien, nouvelle=snapshot_rdv(rdv),
        auteur_id=int(current_user["id"]), motif="Patient arrivé à l'accueil",
    )
    return {
        "rdv_id": rdv.id,
        "patient_id": rdv.patient_id,
        "episode_id": episode.id,
        "dossier_id": dossier.id,
        "statut": rdv.statut,
    }


async def confirmer_presence(db: AsyncSession, current_user: dict, rdv_id: int) -> dict:
    """Présence confirmée (statut `confirme`)."""
    rdv = await _charger_rdv(db, rdv_id, int(current_user["clinic_id"]))
    if rdv.statut != StatutRDV.ARRIVE.value:
        raise ValueError("Prérequis : patient arrivé (statut 'arrive')")
    ancien = snapshot_rdv(rdv)
    rdv.statut = StatutRDV.CONFIRME.value
    await db.flush()
    await journaliser_evenement(
        db, rdv=rdv, type_evenement=EVENEMENT_PRESENCE,
        ancienne=ancien, nouvelle=snapshot_rdv(rdv),
        auteur_id=int(current_user["id"]), motif="Présence confirmée",
    )
    return {"rdv_id": rdv.id, "statut": rdv.statut}


async def confirmer_accord(db: AsyncSession, current_user: dict, rdv_id: int) -> dict:
    """Accord pour être reçu / examiné (statut `accord`) + ouverture de
    l'épisode patient (Bloc 3 : l'épisode naît de l'accueil)."""
    rdv = await _charger_rdv(db, rdv_id, int(current_user["clinic_id"]))
    if rdv.statut not in (StatutRDV.ARRIVE.value, StatutRDV.CONFIRME.value):
        raise ValueError("Prérequis : arrivée et présence confirmées")
    clinic_id = int(current_user["clinic_id"])
    ancien = snapshot_rdv(rdv)
    rdv.statut = StatutRDV.ACCORD.value
    await db.flush()

    # Épisode patient : on réutilise un épisode non clos du patient, sinon
    # on l'ouvre à partir de ce rendez-vous d'origine.
    result = await db.execute(
        select(EpisodePatient).where(
            EpisodePatient.patient_id == rdv.patient_id,
            EpisodePatient.clinic_id == clinic_id,
            EpisodePatient.statut.notin_([StatutEpisode.CLOTURE.value, StatutEpisode.ANNULE.value]),
        ).order_by(EpisodePatient.id.desc())
    )
    episode = result.scalars().first()
    if episode is None:
        episode = EpisodePatient(
            clinic_id=clinic_id,
            patient_id=rdv.patient_id,
            rdv_origine_id=rdv.id,
            statut=StatutEpisode.OUVERT.value,
            ouvert_par_id=int(current_user["id"]),
        )
        db.add(episode)
        await db.flush()
    elif episode.rdv_origine_id is None:
        episode.rdv_origine_id = rdv.id
        await db.flush()

    await journaliser_evenement(
        db, rdv=rdv, type_evenement=EVENEMENT_ACCORD,
        ancienne=ancien, nouvelle=snapshot_rdv(rdv),
        auteur_id=int(current_user["id"]),
        motif=f"Accord recueilli — épisode {episode.id} ouvert",
    )
    return {"rdv_id": rdv.id, "statut": rdv.statut, "episode_id": episode.id}


async def declarer_absence(db: AsyncSession, current_user: dict, rdv_id: int, motif: str) -> dict:
    """Patient absent : le rendez-vous est conservé (statut `no_show`) et son
    historique reste complet. Aucune suppression."""
    if not motif or not motif.strip():
        raise ValueError("Motif d'absence obligatoire")
    rdv = await _charger_rdv(db, rdv_id, int(current_user["clinic_id"]))
    if rdv.statut in (StatutRDV.ANNULE.value, StatutRDV.TERMINE.value):
        raise ValueError(f"Impossible : rendez-vous au statut {rdv.statut}")
    ancien = snapshot_rdv(rdv)
    rdv.statut = StatutRDV.NO_SHOW.value
    rdv.notes_post_acte = (rdv.notes_post_acte or "") + f"\nAbsent : {motif}"
    await db.flush()
    await journaliser_evenement(
        db, rdv=rdv, type_evenement=EVENEMENT_ABSENCE,
        ancienne=ancien, nouvelle=snapshot_rdv(rdv),
        auteur_id=int(current_user["id"]), motif=motif,
    )
    return {"rdv_id": rdv.id, "statut": rdv.statut}


async def remplacer_rdv(
    db: AsyncSession,
    current_user: dict,
    rdv_id: int,
    nouveau_patient_id: int,
    motif: str,
) -> dict:
    """Remplacement après absence : crée un NOUVEAU rendez-vous pour le
    nouveau patient (même créneau / praticien / acte) sans jamais écraser
    l'ancien."""
    if not motif or not motif.strip():
        raise ValueError("Motif de remplacement obligatoire")
    clinic_id = int(current_user["clinic_id"])
    rdv_ancien = await _charger_rdv(db, rdv_id, clinic_id)
    if rdv_ancien.statut != StatutRDV.NO_SHOW.value:
        raise ValueError(
            "Remplacement possible uniquement après absence confirmée (statut no_show)"
        )

    result = await db.execute(
        select(Patient).where(Patient.id == nouveau_patient_id, Patient.clinic_id == clinic_id)
    )
    nouveau_patient = result.scalar_one_or_none()
    if nouveau_patient is None:
        raise ValueError("Nouveau patient introuvable dans cette clinique")
    if nouveau_patient.id == rdv_ancien.patient_id:
        raise ValueError("Le patient remplaçant doit être différent du patient absent")

    nouveau_rdv, _ = await creer_rdv(
        patient_id=nouveau_patient.id,
        praticien_id=rdv_ancien.praticien_id,
        acte_id=rdv_ancien.acte_id,
        date_heure=rdv_ancien.date_heure_debut,
        salle=rdv_ancien.salle,
        db=db,
        created_by=int(current_user["id"]),
        clinic_id=clinic_id,
    )
    nouveau_rdv.source = rdv_ancien.source or "manuel"
    nouveau_rdv.reference = generer_reference(nouveau_rdv)
    nouveau_rdv.remplace_rdv_id = rdv_ancien.id
    await db.flush()
    await db.commit()

    await journaliser_evenement(
        db, rdv=nouveau_rdv, type_evenement=EVENEMENT_CREATION,
        ancienne={}, nouvelle=snapshot_rdv(nouveau_rdv),
        auteur_id=int(current_user["id"]),
        motif=f"Créé en remplacement du RDV {rdv_ancien.id} — {motif}",
    )
    tache = await creer_tache_accueil(
        db, rdv=nouveau_rdv, patient=nouveau_patient, auteur_id=int(current_user["id"])
    )
    await journaliser_evenement(
        db, rdv=rdv_ancien, type_evenement=EVENEMENT_REMPLACEMENT,
        ancienne=snapshot_rdv(rdv_ancien),
        nouvelle={**snapshot_rdv(rdv_ancien), "remplace_par": nouveau_rdv.id},
        auteur_id=int(current_user["id"]), motif=motif,
    )

    return {
        "ancien_rdv_id": rdv_ancien.id,
        "nouveau_rdv_id": nouveau_rdv.id,
        "reference": nouveau_rdv.reference,
        "tache_id": tache.id,
    }


# ── Page « Accueil des patients » ───────────────────────────

async def lister_accueil(
    db: AsyncSession,
    current_user: dict,
    *,
    q: Optional[str] = None,
    source: Optional[str] = None,
    date_debut: Optional[str] = None,
    date_fin: Optional[str] = None,
) -> list[dict]:
    """Recherche par nom, téléphone, référence, rendez-vous (id) et source."""
    clinic_id = int(current_user["clinic_id"])
    query = (
        select(RendezVous, Patient, Utilisateur, ActeMedical)
        .join(Patient, RendezVous.patient_id == Patient.id)
        .join(Utilisateur, RendezVous.praticien_id == Utilisateur.id)
        .outerjoin(ActeMedical, RendezVous.acte_id == ActeMedical.id)
        .where(RendezVous.clinic_id == clinic_id)
    )

    if q and q.strip():
        needle = f"%{q.strip()}%"
        conditions = [
            Patient.nom.ilike(needle),
            Patient.prenom.ilike(needle),
            Patient.telephone.ilike(needle),
            RendezVous.reference.ilike(needle),
        ]
        try:
            conditions.append(RendezVous.id == int(q.strip()))
        except ValueError:
            pass
        query = query.where(or_(*conditions))

    if source:
        query = query.where(RendezVous.source == source)

    if date_debut:
        query = query.where(RendezVous.date_heure_debut >= datetime.fromisoformat(date_debut))
    if date_fin:
        query = query.where(RendezVous.date_heure_debut <= datetime.fromisoformat(date_fin))

    query = query.order_by(RendezVous.date_heure_debut.asc())
    result = await db.execute(query)

    retour = []
    for rdv, patient, praticien, acte in result.all():
        retour.append({
            "id": rdv.id,
            "reference": rdv.reference,
            "patient_id": patient.id,
            "patient_nom": f"{patient.prenom} {patient.nom}",
            "telephone": patient.telephone,
            "source": rdv.source or "manuel",
            "statut": rdv.statut,
            "praticien_nom": f"{praticien.prenom} {praticien.nom}",
            "acte_nom": acte.nom if acte else None,
            "date_heure_debut": rdv.date_heure_debut.isoformat(),
            "salle": rdv.salle,
            "remplace_rdv_id": rdv.remplace_rdv_id,
        })
    return retour
