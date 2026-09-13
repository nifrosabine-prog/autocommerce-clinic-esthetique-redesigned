from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException

from api.v1.episodes import (
    ActeProposalCreate,
    InterventionCreate,
    close_intervention,
    create_intervention,
    mark_intervention_for_validation,
    propose_acte,
    realize_act,
    start_intervention,
    validate_financial_act,
    validate_medical_act,
)
from api.v1.workspace import get_workspace
from models.episode_core import EpisodePatient


async def _episode(db, medecin, patient):
    episode = EpisodePatient(
        clinic_id=1,
        patient_id=patient.id,
        ouvert_par_id=medecin.id,
        ouvert_le=datetime.utcnow(),
    )
    db.add(episode)
    await db.flush()
    return episode


@pytest.mark.asyncio
async def test_professionnel_ne_modifie_pas_le_prix_et_parcours_complet(db, medecin, assistante, patient, acte):
    episode = await _episode(db, medecin, patient)
    user = {"id": medecin.id, "role": "medecin", "clinic_id": 1}
    created = await create_intervention(
        episode.id,
        data=InterventionCreate(professionnel_id=medecin.id),
        current_user=user,
        db=db,
    )
    intervention_id = created["id"]
    line = await propose_acte(
        episode.id,
        intervention_id,
        ActeProposalCreate(acte_id=acte.id, prix_convenu=Decimal("1.000")),
        current_user=user,
        db=db,
    )
    assert Decimal(line["prix_convenu"]) == acte.prix_base
    await validate_medical_act(episode.id, intervention_id, line["id"], user, db)
    await validate_financial_act(
        episode.id, intervention_id, line["id"],
        {"id": assistante.id, "role": "assistante", "clinic_id": 1}, db,
    )
    await start_intervention(episode.id, intervention_id, user, db)
    await realize_act(episode.id, intervention_id, line["id"], user, db)
    await mark_intervention_for_validation(episode.id, intervention_id, user, db)
    closed = await close_intervention(episode.id, intervention_id, user, db)
    assert closed["statut"] == "terminee"


@pytest.mark.asyncio
async def test_validation_financiere_exige_validation_medicale(db, medecin, assistante, patient, acte):
    episode = await _episode(db, medecin, patient)
    user = {"id": medecin.id, "role": "medecin", "clinic_id": 1}
    created = await create_intervention(episode.id, data=InterventionCreate(), current_user=user, db=db)
    line = await propose_acte(episode.id, created["id"], ActeProposalCreate(acte_id=acte.id), user, db)
    with pytest.raises(HTTPException) as exc:
        await validate_financial_act(
            episode.id, created["id"], line["id"],
            {"id": assistante.id, "role": "assistante", "clinic_id": 1}, db,
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_workspace_professionnel_ne_contient_pas_de_bouton_accueil_inaccessible(db, medecin):
    result = await get_workspace({"id": medecin.id, "role": "prestataire", "clinic_id": 1}, db)
    assert result["role"] == "prestataire"
    assert all(card["href"] != "/accueil" for card in result["cards"])
