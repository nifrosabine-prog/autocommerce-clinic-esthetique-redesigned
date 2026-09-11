"""
Service de parrainage — codes et récompenses strictement scoppés par clinique.

Le fallback vers la clinique 1 est conservé uniquement en test/développement,
comme dans le service fidélité. Les appels HTTP de production doivent toujours
fournir le clinic_id du contexte authentifié.
"""
import random
import string
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models.database import Parrainage, Patient
from services import fidelite


def _resolve_clinic_id(clinic_id: Optional[int]) -> int:
    if clinic_id is not None and int(clinic_id) > 0:
        return int(clinic_id)
    settings = get_settings()
    if settings.env in {"test", "development"}:
        return int(settings.clinic_id or 1)
    if settings.is_internal_single_clinic and settings.clinic_id:
        return int(settings.clinic_id)
    raise ValueError("Contexte clinique obligatoire")


class ParrainageService:
    @staticmethod
    def generer_code_unique(nom_patient: str) -> str:
        prefix = (nom_patient or "PAT")[:3].upper()
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
        return f"{prefix}-{suffix}"

    @staticmethod
    async def get_ou_creer_code(
        db: AsyncSession, patient_id: int, clinic_id: Optional[int] = None
    ) -> str:
        clinic_id = _resolve_clinic_id(clinic_id)
        stmt = select(Parrainage).where(
            Parrainage.parrain_patient_id == patient_id,
            Parrainage.clinic_id == clinic_id,
        )
        result = await db.execute(stmt)
        existing = result.scalars().first()
        if existing:
            return existing.code_parrain

        patient = await db.scalar(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.clinic_id == clinic_id,
                Patient.anonymized_at.is_(None),
            )
        )
        if not patient:
            raise ValueError("Patient non trouvé dans cette clinique")

        code = ParrainageService.generer_code_unique(patient.nom)
        new_p = Parrainage(
            clinic_id=clinic_id,
            parrain_patient_id=patient_id,
            code_parrain=code,
            statut="actif",
        )
        db.add(new_p)
        await db.commit()
        return code

    @staticmethod
    async def utiliser_code(
        db: AsyncSession,
        code: str,
        filleul_id: int,
        clinic_id: Optional[int] = None,
    ) -> bool:
        clinic_id = _resolve_clinic_id(clinic_id)
        parrainage = await db.scalar(
            select(Parrainage).where(
                Parrainage.code_parrain == code.strip().upper(),
                Parrainage.statut == "actif",
                Parrainage.clinic_id == clinic_id,
            )
        )
        if not parrainage or parrainage.parrain_patient_id == filleul_id:
            return False

        patients = await db.execute(
            select(Patient).where(
                Patient.id.in_([parrainage.parrain_patient_id, filleul_id]),
                Patient.clinic_id == clinic_id,
                Patient.anonymized_at.is_(None),
            )
        )
        patient_ids = {patient.id for patient in patients.scalars().all()}
        if {parrainage.parrain_patient_id, filleul_id} - patient_ids:
            return False

        parrainage.filleul_patient_id = filleul_id
        parrainage.statut = "utilise"
        parrainage.recompense_attribuee = True

        await fidelite.add_points(
            parrainage.parrain_patient_id,
            50,
            f"Bonus parrainage (filleul #{filleul_id})",
            db,
            clinic_id=clinic_id,
        )
        await fidelite.add_points(
            filleul_id,
            50,
            f"Bonus bienvenue parrainage (code {code})",
            db,
            clinic_id=clinic_id,
        )

        await db.commit()
        return True

    @staticmethod
    async def get_filleuls(
        db: AsyncSession, parrain_id: int, clinic_id: Optional[int] = None
    ) -> List[Parrainage]:
        clinic_id = _resolve_clinic_id(clinic_id)
        stmt = select(Parrainage).where(
            Parrainage.parrain_patient_id == parrain_id,
            Parrainage.clinic_id == clinic_id,
            Parrainage.filleul_patient_id.isnot(None),
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
