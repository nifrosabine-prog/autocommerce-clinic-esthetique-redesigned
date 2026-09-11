from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api-server"
sys.path.insert(0, str(API))
load_dotenv(API / ".env.runtime.staging")

from middleware.auth import get_password_hash  # noqa: E402
from models.database import ClinicSubscription, RoleEnum, Utilisateur  # noqa: E402

SUPER_ADMIN_IDENTIFIER = os.environ.get("SUPER_ADMIN_IDENTIFIER", "anas@superadmin.nt")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD")
if not SUPER_ADMIN_PASSWORD:
    raise RuntimeError("SUPER_ADMIN_PASSWORD doit être fourni par l’environnement, jamais codé dans le dépôt")


async def main() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        user = await db.scalar(select(Utilisateur).where(Utilisateur.email == SUPER_ADMIN_IDENTIFIER))
        if user is None:
            user = Utilisateur(
                clinic_id=1,
                email=SUPER_ADMIN_IDENTIFIER,
                hashed_password=get_password_hash(SUPER_ADMIN_PASSWORD),
                nom="Super",
                prenom="Admin",
                role=RoleEnum.SUPER_ADMIN.value,
                is_active=True,
            )
            db.add(user)
        else:
            user.clinic_id = 1
            user.hashed_password = get_password_hash(SUPER_ADMIN_PASSWORD)
            user.nom = "Super"
            user.prenom = "Admin"
            user.role = RoleEnum.SUPER_ADMIN.value
            user.is_active = True

        subscription = await db.scalar(select(ClinicSubscription).where(ClinicSubscription.clinic_id == 1))
        if subscription is None:
            subscription = ClinicSubscription(
                clinic_id=1,
                clinic_name="Clinique esthétique runtime",
                plan="premium",
                status="active",
                started_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=365),
                monthly_amount="490.000",
                max_users=50,
                notes="Souscription de recette initiale",
            )
            db.add(subscription)
        await db.commit()
        print(f"super_admin_seeded id={user.id if user.id else 'new'} identifier={SUPER_ADMIN_IDENTIFIER}")
        print("password intentionally not printed")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
