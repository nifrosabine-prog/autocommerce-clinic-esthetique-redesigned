from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from api.v1.clinical_operations import (
    CureCreate,
    EvenementCreate,
    SeanceStatusPatch,
    create_adverse_event,
    create_cure,
    update_cure_session,
)
from models.database import EvenementIndesirable, SeanceCure, SuiviPostActe


@pytest.mark.asyncio
async def test_create_cure_generates_sessions(db, medecin, patient, acte):
    payload = CureCreate(
        patient_id=patient.id,
        acte_id=acte.id,
        nom="Peeling visage",
        seances_prevues=3,
        premiere_seance_at=datetime.utcnow() + timedelta(days=1),
    )
    result = await create_cure(payload, {"id": medecin.id, "role": "medecin", "clinic_id": 1}, db)
    assert result["seances_prevues"] == 3
    assert len(result["seances"]) == 3
    assert result["seances"][0]["statut"] == "planifiee"


@pytest.mark.asyncio
async def test_realised_session_creates_one_followup(db, medecin, patient, acte):
    cure = await create_cure(CureCreate(
        patient_id=patient.id, acte_id=acte.id, nom="Cure test", seances_prevues=1,
    ), {"id": medecin.id, "role": "medecin", "clinic_id": 1}, db)
    session_id = cure["seances"][0]["id"]
    session = await db.scalar(select(SeanceCure).where(SeanceCure.id == session_id))
    session.suivi_recommande_le = datetime.utcnow().date() + timedelta(days=7)
    await db.flush()

    await update_cure_session(
        cure_id=cure["id"],
        seance_id=session_id,
        payload=SeanceStatusPatch(statut="realisee"),
        current_user={"id": medecin.id, "role": "medecin", "clinic_id": 1},
        db=db,
    )
    followups = (await db.execute(select(SuiviPostActe).where(SuiviPostActe.seance_id == session_id))).scalars().all()
    assert len(followups) == 1
    assert followups[0].patient_id == patient.id


@pytest.mark.asyncio
async def test_adverse_event_is_scoped_to_authenticated_clinic(db, medecin, patient):
    result = await create_adverse_event(
        EvenementCreate(
            patient_id=patient.id,
            survenu_at=datetime.utcnow(),
            description="Rougeur persistante après le soin",
            gravite="moderee",
        ),
        {"id": medecin.id, "role": "medecin", "clinic_id": 1},
        db,
    )
    event = await db.scalar(select(EvenementIndesirable).where(EvenementIndesirable.id == result["id"]))
    assert event is not None
    assert event.clinic_id == 1


@pytest.mark.asyncio
async def test_cross_clinic_patient_is_rejected(db, medecin, patient):
    from fastapi import HTTPException
    from models.database import Patient

    other_patient = Patient(clinic_id=2, nom="Autre", prenom="Tenant", telephone="+21621111111")
    db.add(other_patient)
    await db.flush()
    with pytest.raises(HTTPException) as exc:
        await create_adverse_event(
            EvenementCreate(
                patient_id=other_patient.id,
                survenu_at=datetime.utcnow(),
                description="Tentative hors tenant",
            ),
            {"id": medecin.id, "role": "medecin", "clinic_id": 1},
            db,
        )
    assert exc.value.status_code == 404
