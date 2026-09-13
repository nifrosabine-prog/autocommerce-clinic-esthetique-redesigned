import hashlib
from pathlib import Path

import pytest
from sqlalchemy import select

from models.database import AuditLogMedical, Patient
from services.documents_medicaux import list_documents, read_document, soft_delete_document, upload_document


@pytest.mark.asyncio
async def test_medical_document_is_encrypted_private_integrity_checked_and_audited(db, medecin, patient):
    user = {"id": medecin.id, "clinic_id": 1, "role": "medecin"}
    raw = b"%PDF-1.4 medical document test"
    created = await upload_document(db, patient.id, user, raw, "compte-rendu.pdf", "application/pdf", "Document clinique", None, None, {})
    assert created["hash_sha256"] == hashlib.sha256(raw).hexdigest()
    item, restored = await read_document(db, patient.id, created["id"], user, {})
    assert restored == raw
    assert Path(item.chemin_chiffre).suffix == ".enc"
    audit = (await db.execute(select(AuditLogMedical))).scalars().all()
    assert any(x.action == "UPLOAD_MEDICAL_DOCUMENT" for x in audit)
    assert any(x.action == "READ_MEDICAL_DOCUMENT" for x in audit)


@pytest.mark.asyncio
async def test_medical_document_rbac_cross_tenant_and_soft_delete(db, assistante, patient):
    user = {"id": assistante.id, "clinic_id": 1, "role": "assistante"}
    with pytest.raises(PermissionError):
        await upload_document(db, patient.id, user, b"x", "x.pdf", "application/pdf", None, None, None, {})
    other = Patient(clinic_id=2, nom="Autre", prenom="Clinique", telephone="+21626666666")
    db.add(other)
    await db.flush()
    with pytest.raises(ValueError):
        await upload_document(db, other.id, {"id": assistante.id, "clinic_id": 1, "role": "medecin"}, b"x", "x.pdf", "application/pdf", None, None, None, {})

    # médecin actif pour vérifier le soft-delete sans supprimer le fichier physiquement
    from models.database import Utilisateur, RoleEnum
    doctor = Utilisateur(clinic_id=1, email="doc-d@clinic.tn", hashed_password="x", nom="D", prenom="Doc", role=RoleEnum.MEDECIN.value)
    db.add(doctor)
    await db.flush()
    doctor_user = {"id": doctor.id, "clinic_id": 1, "role": "medecin"}
    created = await upload_document(db, patient.id, doctor_user, b"x", "x.pdf", "application/pdf", None, None, None, {})
    await soft_delete_document(db, patient.id, created["id"], doctor_user, {})
    assert await list_documents(db, patient.id, doctor_user, {}) == []


@pytest.mark.asyncio
async def test_document_rejects_unsupported_mime(db, medecin, patient):
    with pytest.raises(ValueError):
        await upload_document(db, patient.id, {"id": medecin.id, "clinic_id": 1, "role": "medecin"}, b"x", "x.exe", "application/octet-stream", None, None, None, {})
