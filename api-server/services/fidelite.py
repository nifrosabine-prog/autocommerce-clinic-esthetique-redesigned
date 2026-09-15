"""
Service fidélité — opérations strictement scoppées par clinique.

En production, l'absence de contexte clinique est une erreur de sécurité.
Le fallback vers la clinique 1 est conservé uniquement pour les tests et le
mode développement afin de préserver les appels unitaires historiques.
"""
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models.database import Patient, FideliteTransaction, NiveauFidelite

NIVEAUX_SEUILS = [
    (5000, NiveauFidelite.VIP.value),
    (2000, NiveauFidelite.GOLD.value),
    (500, NiveauFidelite.SILVER.value),
    (0, NiveauFidelite.BRONZE.value),
]


def _niveau_pour(points: int) -> str:
    for seuil, niveau in NIVEAUX_SEUILS:
        if points >= seuil:
            return niveau
    return NiveauFidelite.BRONZE.value


def _resolve_clinic_id(clinic_id: Optional[int]) -> int:
    if clinic_id is not None and int(clinic_id) > 0:
        return int(clinic_id)
    settings = get_settings()
    if settings.env in {"test", "development"}:
        return int(settings.clinic_id or 1)
    if settings.is_internal_single_clinic and settings.clinic_id:
        return int(settings.clinic_id)
    raise ValueError("Contexte clinique obligatoire")


async def _get_patient(
    patient_id: int,
    db: AsyncSession,
    clinic_id: Optional[int] = None,
    lock: bool = False,
) -> Patient:
    clinic_id = _resolve_clinic_id(clinic_id)
    query = select(Patient).where(
        Patient.id == patient_id,
        Patient.clinic_id == clinic_id,
    )
    if lock:
        query = query.with_for_update()
    result = await db.execute(query)
    patient = result.scalar_one_or_none()
    if not patient:
        raise ValueError("Patient non trouvé dans cette clinique")
    return patient


async def add_points(
    patient_id: int,
    points: int,
    motif: str,
    db: AsyncSession,
    reference_id: Optional[int] = None,
    reference_type: Optional[str] = None,
    clinic_id: Optional[int] = None,
) -> FideliteTransaction:
    clinic_id = _resolve_clinic_id(clinic_id)
    if points <= 0:
        raise ValueError("Le nombre de points doit être positif")
    patient = await _get_patient(patient_id, db, clinic_id=clinic_id, lock=True)
    patient.points_fidelite += points
    patient.niveau_fidelite = _niveau_pour(patient.points_fidelite)

    tx = FideliteTransaction(
        clinic_id=clinic_id,
        patient_id=patient_id,
        type="gain",
        points=points,
        solde_apres=patient.points_fidelite,
        motif=motif,
        reference_id=reference_id,
        reference_type=reference_type,
    )
    db.add(tx)
    await db.flush()
    return tx


async def redeem_points(
    patient_id: int,
    points: int,
    motif: str,
    db: AsyncSession,
    clinic_id: Optional[int] = None,
) -> FideliteTransaction:
    clinic_id = _resolve_clinic_id(clinic_id)
    if points <= 0:
        raise ValueError("Le nombre de points doit être positif")
    patient = await _get_patient(patient_id, db, clinic_id=clinic_id, lock=True)
    if points > patient.points_fidelite:
        raise ValueError("Solde de points insuffisant")

    patient.points_fidelite -= points
    patient.niveau_fidelite = _niveau_pour(patient.points_fidelite)
    tx = FideliteTransaction(
        clinic_id=clinic_id,
        patient_id=patient_id,
        type="depense",
        points=-points,
        solde_apres=patient.points_fidelite,
        motif=motif,
    )
    db.add(tx)
    await db.flush()
    return tx


async def get_historique(
    patient_id: int,
    db: AsyncSession,
    clinic_id: Optional[int] = None,
) -> list[FideliteTransaction]:
    clinic_id = _resolve_clinic_id(clinic_id)
    result = await db.execute(
        select(FideliteTransaction)
        .where(
            FideliteTransaction.patient_id == patient_id,
            FideliteTransaction.clinic_id == clinic_id,
        )
        .order_by(FideliteTransaction.created_at.desc())
    )
    return list(result.scalars().all())


async def get_overview(db: AsyncSession, clinic_id: Optional[int] = None, limit: int = 100) -> dict:
    clinic_id = _resolve_clinic_id(clinic_id)
    limit = max(1, min(int(limit), 500))
    total_result = await db.execute(
        select(func.coalesce(func.sum(Patient.points_fidelite), 0)).where(
            Patient.clinic_id == clinic_id,
            Patient.anonymized_at.is_(None),
        )
    )
    total_points = total_result.scalar_one()

    tx_result = await db.execute(
        select(FideliteTransaction, Patient)
        .join(
            Patient,
            (Patient.id == FideliteTransaction.patient_id)
            & (Patient.clinic_id == FideliteTransaction.clinic_id),
        )
        .where(FideliteTransaction.clinic_id == clinic_id)
        .order_by(FideliteTransaction.created_at.desc())
        .limit(limit)
    )
    transactions = [
        {
            "id": tx.id,
            "patient_nom": f"{patient.prenom} {patient.nom}",
            "type": tx.type,
            "points": tx.points,
            "motif": tx.motif,
            "date": tx.created_at,
        }
        for tx, patient in tx_result.all()
    ]
    return {"total_points": total_points, "transactions": transactions}
