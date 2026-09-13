"""Régression : l'agenda interne ne dépend pas de la publication web."""

import pytest

from api.v1.agenda_clinic import list_agenda_actes, list_agenda_praticiens
from models.database import ActeMedical, RoleEnum


@pytest.mark.asyncio
async def test_agenda_catalogue_inclut_les_elements_non_publics(db, medecin, acte):
    medecin.is_public = False
    acte.is_public = False
    await db.flush()

    current_user = {"id": 2, "clinic_id": 1, "role": RoleEnum.ASSISTANTE.value}
    praticiens = await list_agenda_praticiens(db=db, current_user=current_user)
    actes = await list_agenda_actes(db=db, current_user=current_user)

    assert [item["id"] for item in praticiens] == [medecin.id]
    assert [item["id"] for item in actes] == [acte.id]


@pytest.mark.asyncio
async def test_agenda_catalogue_exclut_les_comptes_et_actes_inactifs(db, medecin, acte):
    medecin.is_active = False
    acte.is_active = False
    db.add(ActeMedical(
        clinic_id=1,
        nom="Acte interne actif",
        categorie="soin",
        duree_minutes=45,
        prix_base=acte.prix_base,
        is_public=False,
    ))
    await db.flush()

    current_user = {"id": 2, "clinic_id": 1, "role": RoleEnum.ASSISTANTE.value}
    praticiens = await list_agenda_praticiens(db=db, current_user=current_user)
    actes = await list_agenda_actes(db=db, current_user=current_user)

    assert praticiens == []
    assert [item["nom"] for item in actes] == ["Acte interne actif"]
