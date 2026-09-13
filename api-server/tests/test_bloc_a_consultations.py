from datetime import datetime

import pytest
from pydantic import ValidationError

from api.v1.consultations_medicales import ConsultationPayload
from models.database import AuditLogMedical, Patient
from services.consultations_medicales import create_consultation, get_consultation, update_consultation


@pytest.mark.asyncio
async def test_medecin_creates_consultation_with_authenticated_author_and_audit(db, medecin, patient):
    item = await create_consultation(
        db,
        patient.id,
        {"id": medecin.id, "clinic_id": 1, "role": "medecin"},
        {
            "date_consultation": datetime(2026, 9, 10, 10, 0),
            "motif": "Douleur persistante",
            "diagnostic": "Hypothèse à confirmer",
        },
        {"ip_address": "127.0.0.1"},
    )
    assert item.auteur_id == medecin.id
    assert item.motif_enc != "Douleur persistante"
    result = await db.get(AuditLogMedical, 1)
    assert result.action == "CREATE_CONSULTATION"
    assert result.utilisateur_id == medecin.id

    detail = await get_consultation(
        db, item.id, patient.id,
        {"id": medecin.id, "clinic_id": 1, "role": "medecin"},
        {"ip_address": "127.0.0.1"},
    )
    assert detail["motif"] == "Douleur persistante"
    assert detail["auteur_id"] == medecin.id


@pytest.mark.asyncio
async def test_medecin_can_update_consultation_and_author_cannot_be_changed(db, medecin, patient):
    item = await create_consultation(
        db, patient.id, {"id": medecin.id, "clinic_id": 1, "role": "medecin"},
        {"date_consultation": datetime.utcnow(), "motif": "Initial"}, {},
    )
    detail = await update_consultation(
        db, item.id, patient.id,
        {"id": medecin.id, "clinic_id": 1, "role": "medecin"},
        {"motif": "Corrigé", "auteur_id": 9999}, {},
    )
    assert detail["motif"] == "Corrigé"
    assert detail["auteur_id"] == medecin.id


@pytest.mark.asyncio
async def test_non_medical_role_is_denied_and_cross_tenant_isolation_holds(db, assistante, patient):
    with pytest.raises(PermissionError):
        await create_consultation(
            db, patient.id, {"id": assistante.id, "clinic_id": 1, "role": "assistante"},
            {"date_consultation": datetime.utcnow(), "motif": "interdit"}, {},
        )

    other = Patient(clinic_id=2, nom="Autre", prenom="Clinique", telephone="+21629999999")
    db.add(other)
    await db.flush()
    with pytest.raises(ValueError):
        await create_consultation(
            db, other.id, {"id": assistante.id, "clinic_id": 1, "role": "medecin"},
            {"date_consultation": datetime.utcnow(), "motif": "cross tenant"}, {},
        )


def test_frontend_cannot_supply_author_identity():
    with pytest.raises(ValidationError):
        ConsultationPayload(
            date_consultation=datetime.utcnow(),
            motif="test",
            author_id=123,
        )
