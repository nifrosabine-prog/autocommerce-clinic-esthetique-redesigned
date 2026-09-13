"""Rappels persistants de seuil pour injectables et consommables."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import AlerteStock


def _key_filters(type_article: str, produit_id: Optional[int], lot_id: Optional[int], consommable_id: Optional[int], clinic_id: int):
    return (
        AlerteStock.clinic_id == clinic_id,
        AlerteStock.type_article == type_article,
        AlerteStock.produit_id == produit_id,
        AlerteStock.lot_id == lot_id,
        AlerteStock.consommable_id == consommable_id,
    )


def alert_to_dict(alert: AlerteStock) -> dict:
    return {
        "id": alert.id,
        "clinic_id": alert.clinic_id,
        "type_article": alert.type_article,
        "produit_id": alert.produit_id,
        "lot_id": alert.lot_id,
        "consommable_id": alert.consommable_id,
        "niveau": alert.niveau,
        "article_nom": alert.article_nom,
        "message": alert.message,
        "stock_actuel": float(alert.stock_actuel),
        "seuil": float(alert.seuil),
        "statut": alert.statut,
        "declenchee_le": alert.declenchee_le.isoformat(),
        "acquittee_le": alert.acquittee_le.isoformat() if alert.acquittee_le else None,
    }


async def sync_stock_alert(
    db: AsyncSession, *, clinic_id: int, type_article: str, article_nom: str,
    stock_actuel: Decimal, seuil_alerte: Decimal, stock_minimum: Decimal,
    produit_id: Optional[int] = None, lot_id: Optional[int] = None,
    consommable_id: Optional[int] = None,
) -> Optional[AlerteStock]:
    """Synchronise une alerte : active sous seuil, résolue au retour au-dessus.

    Une seule alerte active existe par article (ou lot injectable) et niveau.
    Une alerte acquittée reste historique ; un nouveau franchissement recrée
    une alerte active, ce qui fournit un rappel fiable sans spammer.
    """
    stock_actuel, seuil_alerte, stock_minimum = map(lambda x: Decimal(str(x)), (stock_actuel, seuil_alerte, stock_minimum))
    niveau = "critique" if stock_actuel <= stock_minimum else "alerte"
    sous_seuil = stock_actuel <= seuil_alerte
    filters = _key_filters(type_article, produit_id, lot_id, consommable_id, clinic_id)
    result = await db.execute(select(AlerteStock).where(*filters, AlerteStock.statut == "active").order_by(AlerteStock.id.desc()))
    active = result.scalars().first()
    if not sous_seuil:
        if active:
            active.statut = "resolue"
            active.acquittee_le = datetime.utcnow()
            await db.flush()
        return None
    message = f"{stock_actuel} unité(s) restante(s) — seuil {seuil_alerte}"
    if active:
        active.niveau = niveau
        active.message = message
        active.stock_actuel = stock_actuel
        active.seuil = seuil_alerte
        await db.flush()
        return active
    alert = AlerteStock(
        clinic_id=clinic_id, type_article=type_article, produit_id=produit_id,
        lot_id=lot_id, consommable_id=consommable_id, niveau=niveau,
        article_nom=article_nom, message=message, stock_actuel=stock_actuel,
        seuil=seuil_alerte, statut="active", declenchee_le=datetime.utcnow(),
    )
    db.add(alert)
    await db.flush()
    return alert


async def list_active_stock_alerts(db: AsyncSession, clinic_id: int, limit: int = 200) -> list[dict]:
    result = await db.execute(
        select(AlerteStock).where(AlerteStock.clinic_id == clinic_id, AlerteStock.statut == "active")
        .order_by(AlerteStock.niveau.desc(), AlerteStock.declenchee_le.desc()).limit(limit)
    )
    return [alert_to_dict(a) for a in result.scalars().all()]


async def acknowledge_stock_alert(db: AsyncSession, alert_id: int, clinic_id: int, user_id: int) -> bool:
    result = await db.execute(select(AlerteStock).where(AlerteStock.id == alert_id, AlerteStock.clinic_id == clinic_id, AlerteStock.statut == "active"))
    alert = result.scalar_one_or_none()
    if not alert:
        return False
    alert.statut = "acquittee"
    alert.acquittee_le = datetime.utcnow()
    alert.acquittee_par_id = user_id
    await db.flush()
    return True
