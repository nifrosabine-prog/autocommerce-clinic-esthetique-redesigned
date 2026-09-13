"""Tests du cœur épisode patient (Bloc 1 + 7 ajustements post-revue).

Portée volontairement limitée à la structure du modèle (relations,
contraintes DB, enums de transition) — les règles métier complètes
(garde-fous de clôture, calcul des affectations de paiement, copie des
lignes lors du versionnage d'un devis...) appartiennent aux services du
Bloc 4 et seront testées à ce moment-là.
"""
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from models.database import (
    ActeCatalogue,
    Base,
    Consentement,
    Facture,
    PhotoClinic,
    RoleEnum,
    Salle,
    SimulationIA,
    SuiviPostActe,
    UtilisationLot,
    Utilisateur,
)
from models.episode_core import (
    Devis,
    EpisodePatient,
    FactureLigne,
    Intervention,
    InterventionActe,
    NotePrivee,
    Paiement,
    PaiementAffectation,
    Prospect,
    StatutDevis,
    StatutEpisode,
    StatutIntervention,
    StatutProspect,
)


def test_import_runtime_enregistre_les_nouvelles_tables():
    """Corrige la lacune runtime relevée en revue : `models/__init__.py`
    doit charger episode_core sans dépendre d'Alembic ou d'un import
    explicite dans chaque routeur."""
    noms_tables = set(Base.metadata.tables.keys())
    for table in (
        "prospects", "episodes_patient", "interventions", "interventions_actes",
        "devis", "devis_lignes", "facture_lignes", "paiements",
        "paiements_affectations", "notes_privees", "notes_partagees",
        "agenda_events", "audit_events",
    ):
        assert table in noms_tables, f"table {table} absente de Base.metadata — import runtime cassé"


def test_entites_cliniques_sont_rattachees_a_lepisode_et_a_lintervention():
    """Le modèle cible doit porter la portée clinique de l'épisode, sans
    perdre les enregistrements historiques qui restent nullable."""
    assert ActeCatalogue is not None
    for model in (PhotoClinic, Consentement, SimulationIA, UtilisationLot, SuiviPostActe):
        assert "episode_id" in model.__table__.c
        assert "intervention_id" in model.__table__.c
    assert "episode_id" in Base.metadata.tables["photos_clinic"].c
    assert "episode_id" in Base.metadata.tables["suivis_post_acte"].c


@pytest.mark.asyncio
async def test_episode_multi_intervention_multi_professionnel(db, medecin, assistante, patient, acte):
    """Le scénario central du Bloc 1 : un épisode regroupe plusieurs
    interventions de professionnels différents, chacune avec son propre
    rendez-vous/salle (ajustement 1)."""
    salle = Salle(clinic_id=1, nom="Salle esthétique", type="esthetique")
    db.add(salle)
    await db.flush()

    episode = EpisodePatient(
        clinic_id=1, patient_id=patient.id,
        ouvert_par_id=assistante.id, ouvert_le=datetime.utcnow(),
    )
    db.add(episode)
    await db.flush()
    assert episode.statut == StatutEpisode.OUVERT.value

    intervention_medecin = Intervention(
        clinic_id=1, episode_id=episode.id, professionnel_id=medecin.id,
        type_intervention="medical",
    )
    intervention_esthe = Intervention(
        clinic_id=1, episode_id=episode.id, professionnel_id=assistante.id,
        type_intervention="esthetique", salle_id=salle.id,
    )
    db.add_all([intervention_medecin, intervention_esthe])
    await db.flush()

    acte_medecin = InterventionActe(
        clinic_id=1, intervention_id=intervention_medecin.id, acte_id=acte.id,
        prix_convenu=Decimal("250.000"), propose_par_id=medecin.id, propose_le=datetime.utcnow(),
    )
    db.add(acte_medecin)
    await db.flush()

    result = await db.execute(select(Intervention).where(Intervention.episode_id == episode.id))
    interventions = result.scalars().all()
    assert len(interventions) == 2
    assert {i.professionnel_id for i in interventions} == {medecin.id, assistante.id}


@pytest.mark.asyncio
async def test_chaine_etats_intervention_acte_realise_exige_accepte_medical(db, medecin, patient, acte):
    """Garde-fou DB (ajustement du Bloc 1 initial, toujours actif en v2) :
    un acte ne peut pas être `realise=true` sans `accepte_medical=true`."""
    episode = EpisodePatient(clinic_id=1, patient_id=patient.id, ouvert_par_id=medecin.id, ouvert_le=datetime.utcnow())
    db.add(episode)
    await db.flush()
    intervention = Intervention(clinic_id=1, episode_id=episode.id, professionnel_id=medecin.id, type_intervention="medical")
    db.add(intervention)
    await db.flush()

    acte_non_accepte = InterventionActe(
        clinic_id=1, intervention_id=intervention.id, acte_id=acte.id,
        propose_par_id=medecin.id, propose_le=datetime.utcnow(),
        realise=True, accepte_medical=False,
    )
    db.add(acte_non_accepte)
    with pytest.raises(IntegrityError):
        await db.flush()


@pytest.mark.asyncio
async def test_paiement_affectation_repartit_sur_plusieurs_lignes(db, medecin, patient, acte):
    """Ajustement 2 : la répartition d'un paiement partiel sur une facture
    multi-actes se lit précisément via PaiementAffectation."""
    facture = Facture(clinic_id=1, patient_id=patient.id, numero_facture="F-TEST-001", total_ttc=Decimal("400.000"))
    db.add(facture)
    await db.flush()

    ligne_botox = FactureLigne(facture_id=facture.id, description="Botox", quantite=1, prix_unitaire=Decimal("300.000"), montant_ligne=Decimal("300.000"))
    ligne_massage = FactureLigne(facture_id=facture.id, description="Massage", quantite=1, prix_unitaire=Decimal("100.000"), montant_ligne=Decimal("100.000"))
    db.add_all([ligne_botox, ligne_massage])
    await db.flush()

    paiement = Paiement(
        clinic_id=1, facture_id=facture.id, montant=Decimal("200.000"), mode="carte",
        encaisse_par_id=medecin.id, encaisse_le=datetime.utcnow(),
    )
    db.add(paiement)
    await db.flush()

    aff_massage = PaiementAffectation(paiement_id=paiement.id, facture_ligne_id=ligne_massage.id, montant_affecte=Decimal("100.000"))
    aff_botox = PaiementAffectation(paiement_id=paiement.id, facture_ligne_id=ligne_botox.id, montant_affecte=Decimal("100.000"))
    db.add_all([aff_massage, aff_botox])
    await db.flush()

    result = await db.execute(select(PaiementAffectation).where(PaiementAffectation.paiement_id == paiement.id))
    affectations = result.scalars().all()
    assert len(affectations) == 2
    assert sum(a.montant_affecte for a in affectations) == Decimal("200.000")
    # Massage soldé (100/100), Botox seulement moitié couvert (100/300) —
    # c'est au service Bloc 4 de calculer ce solde, ce test vérifie
    # uniquement que la donnée nécessaire est bien capturée.


@pytest.mark.asyncio
async def test_paiement_affectation_unique_par_ligne(db, medecin, patient):
    """Contrainte d'unicité : pas deux affectations du même paiement vers
    la même ligne (une seule ligne d'affectation, montant modifiable)."""
    facture = Facture(clinic_id=1, patient_id=patient.id, numero_facture="F-TEST-002", total_ttc=Decimal("100.000"))
    db.add(facture)
    await db.flush()
    ligne = FactureLigne(facture_id=facture.id, description="Soin", quantite=1, prix_unitaire=Decimal("100.000"), montant_ligne=Decimal("100.000"))
    db.add(ligne)
    await db.flush()
    paiement = Paiement(clinic_id=1, facture_id=facture.id, montant=Decimal("100.000"), mode="especes", encaisse_par_id=medecin.id, encaisse_le=datetime.utcnow())
    db.add(paiement)
    await db.flush()

    db.add(PaiementAffectation(paiement_id=paiement.id, facture_ligne_id=ligne.id, montant_affecte=Decimal("50.000")))
    await db.flush()
    db.add(PaiementAffectation(paiement_id=paiement.id, facture_ligne_id=ligne.id, montant_affecte=Decimal("50.000")))
    with pytest.raises(IntegrityError):
        await db.flush()


@pytest.mark.asyncio
async def test_devis_versionnage_conserve_historique(db, medecin, assistante, patient, acte):
    """Ajustement 3 : un devis refusé n'est jamais remis à brouillon — une
    nouvelle version est créée, reliée par devis_parent_id/remplace_devis_id."""
    episode = EpisodePatient(clinic_id=1, patient_id=patient.id, ouvert_par_id=assistante.id, ouvert_le=datetime.utcnow())
    db.add(episode)
    await db.flush()

    devis_v1 = Devis(
        clinic_id=1, episode_id=episode.id, numero_devis="D-TEST-001",
        version=1, statut=StatutDevis.REFUSE.value, cree_par_id=assistante.id,
    )
    db.add(devis_v1)
    await db.flush()

    devis_v2 = Devis(
        clinic_id=1, episode_id=episode.id, numero_devis="D-TEST-002",
        version=2, devis_parent_id=devis_v1.id, remplace_devis_id=devis_v1.id,
        statut=StatutDevis.BROUILLON.value, cree_par_id=assistante.id,
    )
    db.add(devis_v2)
    await db.flush()

    assert devis_v2.devis_parent_id == devis_v1.id
    assert devis_v2.remplace_devis_id == devis_v1.id
    # refuse/expire sont désormais terminaux — plus de retour à brouillon
    assert StatutDevis.transitions_autorisees()[StatutDevis.REFUSE.value] == set()


def test_statut_episode_transitions_incluent_attente_consentement():
    """Ajustement 4."""
    transitions = StatutEpisode.transitions_autorisees()
    assert StatutEpisode.EN_ATTENTE_CONSENTEMENT.value in transitions[StatutEpisode.OUVERT.value]
    # CLOTURE reste listée comme transition possible depuis EN_COURS, mais
    # sa légalité réelle est du ressort du service (documenté, pas testable
    # ici sans le service du Bloc 4).
    assert StatutEpisode.CLOTURE.value in transitions[StatutEpisode.EN_COURS.value]


def test_statut_intervention_a_valider_permet_retour_en_cours():
    """Ajustement 5."""
    transitions = StatutIntervention.transitions_autorisees()
    assert StatutIntervention.A_VALIDER.value in transitions[StatutIntervention.EN_COURS.value]
    assert StatutIntervention.EN_COURS.value in transitions[StatutIntervention.A_VALIDER.value]
    assert StatutIntervention.TERMINEE.value in transitions[StatutIntervention.A_VALIDER.value]


@pytest.mark.asyncio
async def test_note_privee_archivage_sans_suppression(db, medecin, patient, assistante):
    """Ajustement 6 : une note privée se retire par archivage, jamais par
    DELETE — et sa FK episode_id est désormais RESTRICT, pas CASCADE."""
    episode = EpisodePatient(clinic_id=1, patient_id=patient.id, ouvert_par_id=assistante.id, ouvert_le=datetime.utcnow())
    db.add(episode)
    await db.flush()

    note = NotePrivee(clinic_id=1, episode_id=episode.id, auteur_id=medecin.id, contenu_enc="chiffré")
    db.add(note)
    await db.flush()
    assert note.archived_at is None

    note.archived_at = datetime.utcnow()
    note.archived_by_id = medecin.id
    await db.flush()

    # La note existe toujours (pas de suppression physique)
    result = await db.execute(select(NotePrivee).where(NotePrivee.id == note.id))
    assert result.scalar_one().archived_at is not None


@pytest.mark.asyncio
async def test_role_prestataire_avec_specialite(db):
    """Ajustement 7 : rôle générique + specialite existante, pas de
    nouvelle table nécessaire."""
    masseuse = Utilisateur(
        clinic_id=1, email="masseuse@clinic.tn", hashed_password="x",
        nom="Jlassi", prenom="Nour", role=RoleEnum.PRESTATAIRE.value,
        specialite="massage",
    )
    db.add(masseuse)
    await db.flush()
    assert masseuse.role == RoleEnum.PRESTATAIRE.value
    assert masseuse.specialite == "massage"


@pytest.mark.asyncio
async def test_prospect_conversion_vers_patient(db, patient):
    """Prospect converti = patient_id renseigné, jamais supprimé."""
    prospect = Prospect(
        clinic_id=1, nom="Test", telephone="+21699999999",
        statut=StatutProspect.CONVERTI.value, patient_id=patient.id,
    )
    db.add(prospect)
    await db.flush()
    assert prospect.patient_id == patient.id

    prospect_incoherent = Prospect(
        clinic_id=1, nom="Incohérent", telephone="+21688888888",
        statut=StatutProspect.CONVERTI.value, patient_id=None,
    )
    db.add(prospect_incoherent)
    with pytest.raises(IntegrityError):
        await db.flush()
