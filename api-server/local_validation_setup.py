import asyncio
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from models.database import Base, Utilisateur, RoleEnum, Patient, ActeMedical, UtilisateurActe
from models import omnicanal as _omnicanal  # noqa: F401
from models import security as _security  # noqa: F401
from models import workflow_engine as _workflow_engine  # noqa: F401
from models import episode_core as _episode_core  # noqa: F401
from middleware.auth import get_password_hash

DATABASE_URL = os.environ["DATABASE_URL"]

async def main() -> None:
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session.begin() as db:
        admin = await db.scalar(select(Utilisateur).where(Utilisateur.email == "admin@clinic.local"))
        if admin is None:
            db.add(Utilisateur(
                clinic_id=1,
                email="admin@clinic.local",
                hashed_password=get_password_hash("LocalValidationOnly-2026!"),
                nom="Validation",
                prenom="Admin",
                role=RoleEnum.DIRECTRICE.value,
                is_active=True,
            ))
        practitioner = await db.scalar(select(Utilisateur).where(Utilisateur.email == "doctor@clinic.local"))
        if practitioner is None:
            practitioner = Utilisateur(
                clinic_id=1,
                email="doctor@clinic.local",
                hashed_password=get_password_hash("LocalValidationOnly-2026!"),
                nom="Martin",
                prenom="Ada",
                role=RoleEnum.MEDECIN.value,
                specialite="Médecine esthétique",
                is_active=True,
            )
            db.add(practitioner)
            await db.flush()
        acte = await db.scalar(select(ActeMedical).where(ActeMedical.clinic_id == 1, ActeMedical.nom == "Consultation esthétique"))
        if acte is None:
            acte = ActeMedical(
                clinic_id=1,
                nom="Consultation esthétique",
                categorie="consultation",
                duree_minutes=45,
                prix_base=150,
                description="Évaluation initiale",
                is_active=True,
            )
            db.add(acte)
            await db.flush()
        link = await db.scalar(select(UtilisateurActe).where(UtilisateurActe.utilisateur_id == practitioner.id, UtilisateurActe.acte_id == acte.id))
        if link is None:
            db.add(UtilisateurActe(utilisateur_id=practitioner.id, acte_id=acte.id))

        patient = await db.scalar(select(Patient).where(Patient.telephone == "+21620000001"))
        if patient is None:
            db.add(Patient(
                clinic_id=1,
                nom="Validation",
                prenom="Patient",
                telephone="+21620000001",
                email="patient@clinic.local",
                is_active=True,
            ))
    await engine.dispose()
    print("LOCAL_VALIDATION_DB_READY")

if __name__ == "__main__":
    asyncio.run(main())
