"""Tests — services/consentement.py

Règle métier : un consentement n'est valide que s'il est signé
(est_valide=True) ET signé il y a moins de 12 mois.
"""
from datetime import datetime, timedelta

import pytest

from services.consentement import preview_contract_consent, verify_consent, sign_consent
from models.database import Consentement


@pytest.mark.asyncio
async def test_no_consent_returns_false(db, patient, acte):
    assert await verify_consent(patient.id, acte.id, db) is False


@pytest.mark.asyncio
async def test_valid_recent_consent_returns_true(db, patient, acte, consentement_valide):
    assert await verify_consent(patient.id, acte.id, db) is True


@pytest.mark.asyncio
async def test_consent_older_than_12_months_is_invalid(db, patient, acte):
    old_consent = Consentement(
        clinic_id=1, patient_id=patient.id, acte_id=acte.id,
        type_consentement="acte_medical",
        signe_le=datetime.utcnow() - timedelta(days=400),
        methode_signature="tactile", est_valide=True,
    )
    db.add(old_consent)
    await db.flush()

    assert await verify_consent(patient.id, acte.id, db) is False


@pytest.mark.asyncio
async def test_consent_marked_invalid_is_not_accepted(db, patient, acte):
    revoked = Consentement(
        clinic_id=1, patient_id=patient.id, acte_id=acte.id,
        type_consentement="acte_medical", signe_le=datetime.utcnow(),
        methode_signature="tactile", est_valide=False,
    )
    db.add(revoked)
    await db.flush()

    assert await verify_consent(patient.id, acte.id, db) is False


@pytest.mark.asyncio
async def test_consent_for_different_acte_does_not_cover_this_one(db, patient, acte, consentement_valide):
    """Un consentement signé pour l'acte A ne doit pas couvrir l'acte B."""
    autre_acte_id = acte.id + 999  # acte inexistant, simule un acte différent
    assert await verify_consent(patient.id, autre_acte_id, db) is False


@pytest.mark.asyncio
async def test_sign_consent_creates_valid_record_and_sets_patient_rgpd_date(db, patient, acte, tmp_path, monkeypatch):
    from config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    consentement = await sign_consent(
        patient_id=patient.id,
        acte_id=acte.id,
        signature_b64="data:image/png;base64,iVBORw0KGgo=",
        method="tactile",
        ip_address="10.0.0.1",
        db=db,
    )

    assert consentement.est_valide is True
    assert patient.consentement_rgpd_signe_le is not None
    assert await verify_consent(patient.id, acte.id, db) is True


@pytest.mark.asyncio
async def test_sign_consent_supports_simulation_ia_type(db, patient, tmp_path, monkeypatch):
    from config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    consentement = await sign_consent(
        patient_id=patient.id,
        acte_id=None,
        signature_b64="data:image/png;base64,iVBORw0KGgo=",
        method="tactile",
        ip_address="10.0.0.1",
        db=db,
        type_consentement="simulation_ia",
    )

    assert consentement.type_consentement == "simulation_ia"
    assert consentement.est_valide is True
    assert "SIMULATION IA" in consentement.contenu_signe
    assert await verify_consent(patient.id, None, db, type_consentement="simulation_ia") == consentement


@pytest.mark.asyncio
async def test_sign_consent_acte_medical_requires_acte_id(db, patient, tmp_path, monkeypatch):
    from config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    with pytest.raises(ValueError, match="acte_id"):
        await sign_consent(
            patient_id=patient.id,
            acte_id=None,
            signature_b64="data:image/png;base64,iVBORw0KGgo=",
            method="tactile",
            ip_address="10.0.0.1",
            db=db,
            type_consentement="acte_medical",
        )


@pytest.mark.asyncio
async def test_contract_preview_includes_patient_practitioner_act_and_price(db, patient, acte, medecin):
    preview = await preview_contract_consent(
        patient_id=patient.id,
        acte_ids=[acte.id],
        praticien_id=medecin.id,
        clinic_id=1,
        db=db,
    )

    assert patient.prenom in preview["contenu"]
    assert medecin.prenom in preview["contenu"]
    assert acte.nom in preview["contenu"]
    assert preview["snapshot"]["actes"] == [
        {"id": acte.id, "nom": acte.nom, "prix": 250.0, "devise": "DT"}
    ]


@pytest.mark.asyncio
async def test_contract_signature_freezes_snapshot_and_practitioner(db, patient, acte, medecin, tmp_path, monkeypatch):
    from config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    consentement = await sign_consent(
        patient_id=patient.id,
        acte_id=acte.id,
        acte_ids=[acte.id],
        signature_b64="data:image/png;base64,iVBORw0KGgo=",
        method="tactile",
        ip_address="10.0.0.2",
        db=db,
        praticien_id=medecin.id,
        attestation_praticien=True,
        signature_praticien_b64="data:image/png;base64,iVBORw0KGgo=",
        clinic_id=1,
    )

    assert consentement.contrat_snapshot["patient"]["nom_complet"] == f"{patient.prenom} {patient.nom}"
    assert consentement.contrat_snapshot["praticien"]["id"] == medecin.id
    assert consentement.contrat_snapshot["actes"][0]["id"] == acte.id
    assert consentement.praticien_signataire_id == medecin.id
    assert consentement.attestation_praticien is True
    assert consentement.signature_praticien_base64.startswith("data:image/png")
