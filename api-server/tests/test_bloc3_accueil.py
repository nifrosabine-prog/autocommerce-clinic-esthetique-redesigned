"""
Tests Bloc 3 — Agenda, réservations, CRM (prospects) et accueil patient.

Couvre les critères d'acceptation du cahier des charges :
  - un RDV Internet est visible dans l'agenda et le CRM ;
  - un RDV WhatsApp suit le même modèle qu'un RDV manuel (seule la source diffère) ;
  - l'assistante peut confirmer arrivée, présence et accord d'examen ;
  - une absence conserve son historique (aucune suppression) ;
  - un remplacement crée un nouveau RDV sans écraser l'ancien ;
  - mises à jour : CRM (prospect), tâches de l'assistante, épisode patient ;
  - toute modification importante journalise un événement d'agenda
    (ancienne valeur, nouvelle valeur, auteur, date, motif).
"""

from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import select

from models.database import (
    Patient, Utilisateur, ActeMedical, RendezVous, DossierMedical, StatutRDV,
)
from models.episode_core import Prospect, StatutProspect, EpisodePatient, RdvEvenement
from models.security import TacheInterneAssistant
from services import parcours_arrivee


@pytest_asyncio.fixture
async def base_clinic(db):
    """Praticien + acte + deux patients de base (SQLite en mémoire via conftest)."""
    praticien = Utilisateur(
        email="dr.bloc3@clinic.local", hashed_password="x",
        nom="Martin", prenom="Dr", role="medecin", clinic_id=1, is_active=True,
    )
    db.add(praticien)
    await db.flush()

    acte = ActeMedical(
        clinic_id=1, nom="Massage bien-être", categorie="massage",
        duree_minutes=30, prix_base=50, is_active=True,
    )
    db.add(acte)
    await db.flush()

    p1 = Patient(clinic_id=1, nom="Durand", prenom="Alice",
                 telephone="+33610000001", source_acquisition="manuel")
    p2 = Patient(clinic_id=1, nom="Durand", prenom="Bob",
                 telephone="+33610000002", source_acquisition="manuel")
    db.add_all([p1, p2])
    await db.flush()

    return {
        "praticien": praticien,
        "acte": acte,
        "p1": p1,
        "p2": p2,
        "assistante": {"id": 10, "role": "assistante", "clinic_id": 1},
    }


async def _reserver(db, base, source="internet", heure=10):
    return await parcours_arrivee.creer_rdv_complet(
        db, base["assistante"],
        source=source,
        nom="Durand", prenom="Alice",
        telephone=base["p1"].telephone,
        email="alice.durand@example.fr",
        acte_id=base["acte"].id,
        praticien_id=base["praticien"].id,
        date_heure=datetime(2026, 9, 15, heure, 0),
        motif=f"Réservation {source}",
    )


# ── 1. Un RDV Internet est visible dans l'agenda et le CRM ──

async def test_rdv_internet_visible_agenda_et_crm(db, base_clinic):
    result = await _reserver(db, base_clinic, source="internet")

    rdv = await db.get(RendezVous, result["rdv_id"])
    assert rdv.statut == StatutRDV.PLANIFIE.value
    assert rdv.source == "internet"
    assert rdv.reference and rdv.reference.startswith("RDV1-")

    # Agenda : visible dans la liste d'accueil.
    accueil = await parcours_arrivee.lister_accueil(
        db, base_clinic["assistante"], q=rdv.reference
    )
    assert any(r["id"] == rdv.id for r in accueil)

    # CRM : prospect créé et relié au patient.
    prospect = await db.scalar(
        select(Prospect).where(
            Prospect.clinic_id == 1,
            Prospect.telephone == base_clinic["p1"].telephone,
        )
    )
    assert prospect is not None
    assert prospect.statut == StatutProspect.QUALIFIE.value
    assert prospect.patient_id == base_clinic["p1"].id

    # Tâche d'accueil créée pour l'assistante.
    tache = await db.scalar(select(TacheInterneAssistant))
    assert tache is not None
    assert base_clinic["p1"].id == tache.patient_id


# ── 2. Un RDV WhatsApp suit le même modèle qu'un RDV manuel ──

async def test_rdv_whatsapp_meme_modele_que_manuel(db, base_clinic):
    r_wa = await _reserver(db, base_clinic, source="whatsapp", heure=10)
    r_man = await _reserver(db, base_clinic, source="manuel", heure=11)
    # Deuxièmes réservations pour Alice : créneaux distincts pour éviter le conflit.

    rdv_wa = await db.get(RendezVous, r_wa["rdv_id"])
    rdv_man = await db.get(RendezVous, r_man["rdv_id"])
    assert rdv_wa.source == "whatsapp"
    assert rdv_man.source == "manuel"
    # Même structure de sortie : référence, statut, tache, prospect.
    assert set(r_wa.keys()) == set(r_man.keys())
    assert r_wa["reference"] and r_man["reference"]


# ── 3. Flux d'arrivée : arrivée → présence → accord → épisode ──

async def test_flux_arrivee_presence_accord_ouvre_episode(db, base_clinic):
    result = await _reserver(db, base_clinic)
    rdv_id = result["rdv_id"]

    etape1 = await parcours_arrivee.confirmer_arrivee(db, base_clinic["assistante"], rdv_id)
    assert etape1["statut"] == StatutRDV.ARRIVE.value
    assert etape1["episode_id"]
    assert etape1["dossier_id"]

    dossier = await db.get(DossierMedical, etape1["dossier_id"])
    assert dossier is not None
    assert dossier.patient_id == base_clinic["p1"].id
    assert dossier.rdv_id == rdv_id
    assert dossier.episode_id == etape1["episode_id"]
    assert dossier.acte_id == base_clinic["acte"].id
    assert dossier.statut_clinique == "brouillon"

    # Une arrivée répétée ne doit pas créer un second dossier partagé.
    etape1_rejouee = await parcours_arrivee.confirmer_arrivee(
        db, base_clinic["assistante"], rdv_id
    )
    assert etape1_rejouee["dossier_id"] == dossier.id
    dossiers = (await db.execute(
        select(DossierMedical).where(DossierMedical.episode_id == etape1["episode_id"])
    )).scalars().all()
    assert len(dossiers) == 1

    etape2 = await parcours_arrivee.confirmer_presence(db, base_clinic["assistante"], rdv_id)
    assert etape2["statut"] == StatutRDV.CONFIRME.value

    etape3 = await parcours_arrivee.confirmer_accord(db, base_clinic["assistante"], rdv_id)
    assert etape3["statut"] == StatutRDV.ACCORD.value
    assert etape3["episode_id"]

    # L'épisode est né de l'accueil (rdv_origine_id).
    episode = await db.get(EpisodePatient, etape3["episode_id"])
    assert episode.patient_id == base_clinic["p1"].id
    assert episode.rdv_origine_id == rdv_id
    assert episode.statut == "ouvert"


async def test_presence_impossible_sans_arrivee(db, base_clinic):
    result = await _reserver(db, base_clinic)
    with pytest.raises(ValueError):
        await parcours_arrivee.confirmer_presence(db, base_clinic["assistante"], result["rdv_id"])


# ── 4. Absence : historique conservé ────────────────────────

async def test_absence_conserve_historique(db, base_clinic):
    result = await _reserver(db, base_clinic)
    rdv_id = result["rdv_id"]

    absence = await parcours_arrivee.declarer_absence(
        db, base_clinic["assistante"], rdv_id, motif="Non venue sans prévenir"
    )
    assert absence["statut"] == StatutRDV.NO_SHOW.value

    # Le rendez-vous existe toujours (jamais supprimé).
    rdv = await db.get(RendezVous, rdv_id)
    assert rdv is not None
    assert rdv.statut == StatutRDV.NO_SHOW.value
    assert "Non venue sans prévenir" in (rdv.notes_post_acte or "")

    # L'historique contient création + absence.
    evenements = await parcours_arrivee.evenements_rdv(db, rdv_id, 1)
    types = [e["type_evenement"] for e in evenements]
    assert "creation" in types
    assert "absence" in types
    ev_absence = next(e for e in evenements if e["type_evenement"] == "absence")
    assert ev_absence["motif"] == "Non venue sans prévenir"
    assert ev_absence["auteur_id"] == 10


# ── 5. Remplacement : nouveau RDV sans écrasement ───────────

async def test_remplacement_cree_nouveau_rdv_sans_ecraser(db, base_clinic):
    result = await _reserver(db, base_clinic)
    rdv_id = result["rdv_id"]
    await parcours_arrivee.declarer_absence(
        db, base_clinic["assistante"], rdv_id, motif="Absent"
    )

    remplacement = await parcours_arrivee.remplacer_rdv(
        db, base_clinic["assistante"], rdv_id,
        nouveau_patient_id=base_clinic["p2"].id, motif="Patient remplaçant (Bob)",
    )

    # Nouveau RDV créé pour Bob.
    nouveau = await db.get(RendezVous, remplacement["nouveau_rdv_id"])
    assert nouveau.patient_id == base_clinic["p2"].id
    assert nouveau.remplace_rdv_id == rdv_id

    # L'ANCIEN rendez-vous n'est PAS écrasé : toujours no_show, patient Alice.
    ancien = await db.get(RendezVous, rdv_id)
    assert ancien is not None
    assert ancien.statut == StatutRDV.NO_SHOW.value
    assert ancien.patient_id == base_clinic["p1"].id

    # Même créneau/praticien/acte que l'ancien.
    assert nouveau.date_heure_debut == ancien.date_heure_debut
    assert nouveau.praticien_id == ancien.praticien_id
    assert nouveau.acte_id == ancien.acte_id

    # Historiques des deux rendez-vous alimentés.
    types_ancien = [e["type_evenement"] for e in
                    await parcours_arrivee.evenements_rdv(db, rdv_id, 1)]
    assert "remplacement" in types_ancien
    types_nouveau = [e["type_evenement"] for e in
                     await parcours_arrivee.evenements_rdv(db, nouveau.id, 1)]
    assert "creation" in types_nouveau


async def test_remplacement_impossible_sans_absence(db, base_clinic):
    result = await _reserver(db, base_clinic)
    with pytest.raises(ValueError):
        await parcours_arrivee.remplacer_rdv(
            db, base_clinic["assistante"], result["rdv_id"],
            nouveau_patient_id=base_clinic["p2"].id, motif="Test",
        )


# ── 6. Journal d'agenda : ancienne/nouvelle valeur, auteur, date ──

async def test_evenement_journalise_ancienne_nouvelle_valeur(db, base_clinic):
    result = await _reserver(db, base_clinic)
    evenements = await parcours_arrivee.evenements_rdv(db, result["rdv_id"], 1)
    assert len(evenements) == 1
    ev = evenements[0]
    assert ev["type_evenement"] == "creation"
    assert ev["auteur_id"] == 10
    assert ev["motif"] == "Réservation internet"
    assert '"statut": "planifie"' in ev["nouvelle_valeur"]
    assert ev["cree_le"]  # date présente


# ── 7. Détection de doublons ────────────────────────────────

async def test_detection_doublons_par_telephone(db, base_clinic):
    await _reserver(db, base_clinic)
    doublons = await parcours_arrivee.rechercher_doublons(
        db, clinic_id=1, telephone=base_clinic["p1"].telephone
    )
    assert len(doublons["patients"]) >= 1
    assert doublons["patients"][0]["id"] == base_clinic["p1"].id


async def test_detection_doublons_par_nom_prenom(db, base_clinic):
    doublons = await parcours_arrivee.rechercher_doublons(
        db, clinic_id=1, nom="Durand", prenom="Bob"
    )
    assert len(doublons["patients"]) >= 1


# ── 8. Référence générée et stable ──────────────────────────

async def test_reference_generique(db, base_clinic):
    result = await _reserver(db, base_clinic)
    rdv = await db.get(RendezVous, result["rdv_id"])
    assert rdv.reference == parcours_arrivee.generer_reference(rdv)
