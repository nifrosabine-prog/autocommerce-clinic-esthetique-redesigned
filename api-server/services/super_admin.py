from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis
from prometheus_client import REGISTRY
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models.database import (
    ClinicSetting,
    ClinicSubscription,
    Facture,
    Patient,
    RendezVous,
    StatutFacture,
    Utilisateur,
)
from services.celery_app import celery

settings = get_settings()


def _decimal(value: Any) -> float:
    return float(value or Decimal("0"))


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


async def _clinic_ids(db: AsyncSession) -> list[int]:
    ids: set[int] = set()
    for model in (Utilisateur, Patient, ClinicSetting, ClinicSubscription):
        rows = await db.execute(select(model.clinic_id).distinct())
        ids.update(int(row[0]) for row in rows if row[0] is not None)
    return sorted(ids) or [1]


async def list_clinics(db: AsyncSession) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for clinic_id in await _clinic_ids(db):
        subscription = await db.scalar(select(ClinicSubscription).where(ClinicSubscription.clinic_id == clinic_id))
        user_count = await db.scalar(select(func.count(Utilisateur.id)).where(Utilisateur.clinic_id == clinic_id)) or 0
        active_users = await db.scalar(select(func.count(Utilisateur.id)).where(Utilisateur.clinic_id == clinic_id, Utilisateur.is_active.is_(True))) or 0
        patient_count = await db.scalar(select(func.count(Patient.id)).where(Patient.clinic_id == clinic_id)) or 0
        last_access = await db.scalar(select(func.max(Utilisateur.last_login)).where(Utilisateur.clinic_id == clinic_id))
        revenue = await db.scalar(
            select(func.sum(Facture.total_ttc)).where(
                Facture.clinic_id == clinic_id,
                Facture.statut == StatutFacture.PAYEE.value,
            )
        )
        result.append({
            "clinic_id": clinic_id,
            "name": subscription.clinic_name if subscription else f"Clinique {clinic_id}",
            "status": subscription.status if subscription else "unconfigured",
            "plan": subscription.plan if subscription else None,
            "users": int(user_count),
            "active_users": int(active_users),
            "patients": int(patient_count),
            "revenue": _decimal(revenue),
            "last_access": _iso(last_access),
            "subscription_id": subscription.id if subscription else None,
            "expires_at": _iso(subscription.expires_at) if subscription else None,
        })
    return result


async def list_all_users(db: AsyncSession) -> list[dict[str, Any]]:
    rows = await db.execute(select(Utilisateur).order_by(Utilisateur.clinic_id, Utilisateur.nom, Utilisateur.prenom))
    return [
        {
            "id": user.id,
            "clinic_id": user.clinic_id,
            "email": user.email,
            "nom": user.nom,
            "prenom": user.prenom,
            "role": str(user.role),
            "is_active": user.is_active,
            "last_login": _iso(user.last_login),
            "created_at": _iso(user.created_at),
        }
        for user in rows.scalars().all()
    ]


async def get_clinic_stats(db: AsyncSession, clinic_id: int) -> dict[str, Any]:
    clinics = await list_clinics(db)
    clinic = next((item for item in clinics if item["clinic_id"] == clinic_id), None)
    if clinic is None:
        return {"clinic_id": clinic_id, "exists": False}
    appointments = await db.scalar(select(func.count(RendezVous.id)).where(RendezVous.clinic_id == clinic_id)) or 0
    paid_revenue = await db.scalar(select(func.sum(Facture.total_ttc)).where(Facture.clinic_id == clinic_id, Facture.statut == StatutFacture.PAYEE.value))
    return {**clinic, "exists": True, "appointments": int(appointments), "paid_revenue": _decimal(paid_revenue)}


async def list_subscriptions(db: AsyncSession) -> list[dict[str, Any]]:
    rows = await db.execute(select(ClinicSubscription).order_by(ClinicSubscription.clinic_id))
    return [
        {
            "id": item.id,
            "clinic_id": item.clinic_id,
            "clinic_name": item.clinic_name,
            "plan": item.plan,
            "status": item.status,
            "started_at": _iso(item.started_at),
            "expires_at": _iso(item.expires_at),
            "monthly_amount": _decimal(item.monthly_amount),
            "max_users": item.max_users,
            "notes": item.notes,
            "last_payment_at": _iso(item.last_payment_at),
        }
        for item in rows.scalars().all()
    ]


async def update_subscription(db: AsyncSession, subscription_id: int, changes: dict[str, Any]) -> dict[str, Any] | None:
    item = await db.scalar(select(ClinicSubscription).where(ClinicSubscription.id == subscription_id))
    if item is None:
        return None
    allowed = {"clinic_name", "plan", "status", "expires_at", "monthly_amount", "max_users", "notes", "last_payment_at"}
    for key, value in changes.items():
        if key in allowed and value is not None:
            setattr(item, key, value)
    await db.flush()
    return (await list_subscriptions(db))[next(i for i, row in enumerate(await list_subscriptions(db)) if row["id"] == subscription_id)]


async def get_system_health() -> dict[str, Any]:
    started = time.perf_counter()
    database = {"status": "unknown", "latency_ms": None}
    redis_health = {"status": "unknown", "latency_ms": None}
    celery_health = {"status": "unknown", "workers": 0, "worker_names": []}

    try:
        from models.database import get_async_engine
        engine = get_async_engine(settings.database_url)
        async with engine.connect() as connection:
            t0 = time.perf_counter()
            await connection.execute(text("SELECT 1"))
            database = {"status": "ok", "latency_ms": round((time.perf_counter() - t0) * 1000, 2)}
    except Exception as exc:
        database = {"status": "error", "latency_ms": None, "detail": str(exc)[:200]}

    try:
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        t0 = time.perf_counter()
        await redis.ping()
        redis_health = {"status": "ok", "latency_ms": round((time.perf_counter() - t0) * 1000, 2)}
        await redis.aclose()
    except Exception as exc:
        redis_health = {"status": "error", "latency_ms": None, "detail": str(exc)[:200]}

    try:
        inspector = celery.control.inspect(timeout=1.0)
        active = await asyncio.to_thread(inspector.ping) or {}
        names = sorted(active.keys())
        celery_health = {"status": "ok" if names else "degraded", "workers": len(names), "worker_names": names}
    except Exception as exc:
        celery_health = {"status": "error", "workers": 0, "worker_names": [], "detail": str(exc)[:200]}

    return {
        "checked_at": datetime.utcnow().isoformat(),
        "api": {"status": "ok", "latency_ms": round((time.perf_counter() - started) * 1000, 2)},
        "database": database,
        "redis": redis_health,
        "celery": celery_health,
    }


async def get_performance_metrics(db: AsyncSession) -> dict[str, Any]:
    since = datetime.utcnow() - timedelta(hours=24)
    active_users = await db.scalar(select(func.count()).select_from(Utilisateur).where(Utilisateur.last_login >= since)) or 0
    total_requests = 0.0
    errors_4xx = 0.0
    errors_5xx = 0.0
    duration_sum = 0.0
    duration_count = 0.0
    try:
        for family in REGISTRY.collect():
            if family.name == "http_requests":
                for sample in family.samples:
                    if sample.name != "http_requests_total":
                        continue
                    value = float(sample.value)
                    total_requests += value
                    status = str(sample.labels.get("status", ""))
                    if status == "4xx":
                        errors_4xx += value
                    elif status == "5xx":
                        errors_5xx += value
            elif family.name == "http_request_duration_seconds":
                for sample in family.samples:
                    if sample.name.endswith("_sum"):
                        duration_sum += float(sample.value)
                    elif sample.name.endswith("_count"):
                        duration_count += float(sample.value)
    except Exception:
        # Les métriques restent un enrichissement non bloquant du control plane.
        pass
    process_start = REGISTRY.get_sample_value("process_start_time_seconds") or time.time()
    elapsed_minutes = max((time.time() - process_start) / 60, 1 / 60)
    average_ms = round((duration_sum / duration_count) * 1000, 2) if duration_count else None
    return {
        "window": "process_lifetime",
        "requests_proxy": int(total_requests),
        "requests_total": int(total_requests),
        "requests_per_minute": round(total_requests / elapsed_minutes, 2),
        "active_users": int(active_users),
        "average_response_ms": average_ms,
        "error_rate_4xx": round(errors_4xx / total_requests * 100, 2) if total_requests else 0,
        "error_rate_5xx": round(errors_5xx / total_requests * 100, 2) if total_requests else 0,
        "note": "Mesures Prometheus cumulées depuis le démarrage de l’API.",
    }


async def get_dashboard(db: AsyncSession) -> dict[str, Any]:
    clinics = await list_clinics(db)
    users = await list_all_users(db)
    subscriptions = await list_subscriptions(db)
    paid_revenue = await db.scalar(select(func.sum(Facture.total_ttc)).where(Facture.statut == StatutFacture.PAYEE.value))
    active_clinics = sum(1 for clinic in clinics if clinic["status"] in {"active", "trial"})
    alerts = [
        {"type": "subscription", "severity": "warning", "message": f"{clinic['name']} n’a pas de souscription configurée."}
        for clinic in clinics if clinic["subscription_id"] is None
    ]
    return {
        "kpis": {
            "clinics_total": len(clinics),
            "clinics_active": active_clinics,
            "users_total": len(users),
            "revenue_paid": _decimal(paid_revenue),
            "subscriptions_total": len(subscriptions),
        },
        "clinics": clinics,
        "alerts": alerts,
        "generated_at": datetime.utcnow().isoformat(),
    }
