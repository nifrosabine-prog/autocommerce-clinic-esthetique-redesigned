import asyncio
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from config import get_settings
from middleware.auth import get_password_hash
from models.database import Utilisateur, RoleEnum

USERS = [
    ("estheticienne.qa@autoclinique.test", "Esthéticienne", "Salma", RoleEnum.ESTHETICIENNE.value, "Esthétique"),
    ("assistante.qa@autoclinique.test", "Assistante", "Amel", RoleEnum.ASSISTANTE.value, "Accueil"),
]

async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        for email, nom, prenom, role, specialite in USERS:
            user = (await db.execute(select(Utilisateur).where(Utilisateur.email == email))).scalar_one_or_none()
            if user is None:
                user = Utilisateur(clinic_id=1, email=email, nom=nom, prenom=prenom, role=role, is_active=True, is_public=True, specialite=specialite, hashed_password=get_password_hash("RoleQA-2026-Secure!"))
                db.add(user)
            else:
                user.role = role
                user.is_active = True
                user.is_public = True
                user.hashed_password = get_password_hash("RoleQA-2026-Secure!")
        await db.commit()
    await engine.dispose()
    print("QA users provisioned")

if __name__ == "__main__":
    asyncio.run(main())
