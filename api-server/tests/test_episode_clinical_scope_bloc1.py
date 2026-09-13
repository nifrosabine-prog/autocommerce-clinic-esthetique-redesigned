from datetime import datetime
from io import BytesIO

import pytest
from PIL import Image

from models.database import Consentement, PhotoClinic
from models.episode_core import EpisodePatient, Intervention
from services.clinical_scope import validate_episode_intervention_scope
from services.consentement import verify_consent
from services.photos_clinic import upload_photo


async def _episode_and_intervention(db, patient, medecin):
    episode = EpisodePatient(
        clinic_id=1,
        patient_id=patient.id,
        ouvert_par_id=medecin.id,
        ouvert_le=datetime.utcnow(),
    )
    db.add(episode)
    await db.flush()
    intervention = Intervention(
        clinic_id=1,
        episode_id=episode.id,
        professionnel_id=medecin.id,
        type_intervention="medical",
    )
    db.add(intervention)
    await db.flush()
    return episode, intervention


def _jpeg_bytes():
    image = Image.new("RGB", (32, 32), "white")
    buf = BytesIO()
    image.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_scope_rejette_episode_dune_autre_clinique(db, patient, medecin):
    episode, intervention = await _episode_and_intervention(db, patient, medecin)
    with pytest.raises(ValueError, match="Épisode introuvable"):
        await validate_episode_intervention_scope(
            db,
            patient_id=patient.id,
            clinic_id=2,
            episode_id=episode.id,
            intervention_id=intervention.id,
        )


@pytest.mark.asyncio
async def test_scope_rejette_intervention_hors_episode(db, patient, medecin):
    episode_a, _ = await _episode_and_intervention(db, patient, medecin)
    episode_b, intervention_b = await _episode_and_intervention(db, patient, medecin)
    with pytest.raises(ValueError, match="Intervention introuvable"):
        await validate_episode_intervention_scope(
            db,
            patient_id=patient.id,
            clinic_id=1,
            episode_id=episode_a.id,
            intervention_id=intervention_b.id,
        )


@pytest.mark.asyncio
async def test_upload_photo_persiste_episode_et_intervention(db, patient, medecin, consentement_valide, tmp_path, monkeypatch):
    from config import get_settings
    monkeypatch.setattr(get_settings(), "photos_dir", tmp_path)
    episode, intervention = await _episode_and_intervention(db, patient, medecin)
    photo = await upload_photo(
        patient_id=patient.id,
        dossier_id=None,
        type_photo="avant",
        zone="visage",
        angle="face",
        file_bytes=_jpeg_bytes(),
        mime_type="image/jpeg",
        prise_par_id=medecin.id,
        db=db,
        clinic_id=1,
        episode_id=episode.id,
        intervention_id=intervention.id,
    )
    assert photo.episode_id == episode.id
    assert photo.intervention_id == intervention.id
    assert await db.get(PhotoClinic, photo.id) is not None


@pytest.mark.asyncio
async def test_verification_consentement_est_limitee_a_lepisode(db, patient, acte, medecin):
    episode_a = EpisodePatient(clinic_id=1, patient_id=patient.id, ouvert_par_id=medecin.id, ouvert_le=datetime.utcnow())
    episode_b = EpisodePatient(clinic_id=1, patient_id=patient.id, ouvert_par_id=medecin.id, ouvert_le=datetime.utcnow())
    db.add_all([episode_a, episode_b])
    await db.flush()
    consent = Consentement(
        clinic_id=1,
        patient_id=patient.id,
        episode_id=episode_a.id,
        acte_id=acte.id,
        type_consentement="simulation_ia",
        signe_le=datetime.utcnow(),
        methode_signature="tactile",
        est_valide=True,
    )
    db.add(consent)
    await db.flush()
    assert await verify_consent(patient.id, None, db, type_consentement="simulation_ia", clinic_id=1, episode_id=episode_a.id)
    assert not await verify_consent(patient.id, None, db, type_consentement="simulation_ia", clinic_id=1, episode_id=episode_b.id)
