"""Tests des rappels persistants de seuil stock."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from models.database import AlerteStock, Consommable
from services.consommables import ConsommableService
from services.stock_alerts import acknowledge_stock_alert, list_active_stock_alerts
from services.stock_injectable import _check_single_lot_alert


@pytest.mark.asyncio
async def test_consommable_movement_creates_deduplicated_alert(db, assistante):
    item = Consommable(
        clinic_id=1, nom="Gants", categorie="protection", unite="boîte",
        stock_actuel=Decimal("5"), seuil_alerte=Decimal("5"),
        stock_minimum=Decimal("4"), prix_unitaire=Decimal("1"), is_active=True,
    )
    db.add(item)
    await db.flush()

    await ConsommableService.add_mouvement(db, item.id, "sortie", 1, assistante.id)
    await ConsommableService.add_mouvement(db, item.id, "sortie", 1, assistante.id)

    alerts = await list_active_stock_alerts(db, 1)
    matching = [a for a in alerts if a["consommable_id"] == item.id]
    assert len(matching) == 1
    assert matching[0]["niveau"] == "critique"


@pytest.mark.asyncio
async def test_injectable_alert_can_be_acknowledged(db, produit, lot):
    produit.stock_alerte = Decimal("20")
    produit.stock_minimum = Decimal("5")
    lot.quantite_restante = Decimal("10")
    await db.flush()

    alert = await _check_single_lot_alert(lot, produit, db)
    assert alert is not None
    assert alert.type_article == "injectable"
    assert await acknowledge_stock_alert(db, alert.id, 1, 1) is True
    await db.commit()
    assert await list_active_stock_alerts(db, 1) == []


@pytest.mark.asyncio
async def test_restock_resolves_active_consumable_alert(db, assistante):
    item = Consommable(
        clinic_id=1, nom="Compresses", categorie="soin", unite="paquet",
        stock_actuel=Decimal("1"), seuil_alerte=Decimal("5"),
        stock_minimum=Decimal("2"), prix_unitaire=Decimal("1"), is_active=True,
    )
    db.add(item)
    await db.flush()
    await ConsommableService.add_mouvement(db, item.id, "sortie", 1, assistante.id)
    assert len(await list_active_stock_alerts(db, 1)) == 1
    await ConsommableService.add_mouvement(db, item.id, "entree", 10, assistante.id)
    assert await list_active_stock_alerts(db, 1) == []
    assert (await db.scalar(select(AlerteStock).where(AlerteStock.consommable_id == item.id))).statut == "resolue"
