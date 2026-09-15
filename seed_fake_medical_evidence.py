import asyncio
import base64
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import get_settings
from models.database import Utilisateur, Consentement, PhotoClinic, normalize_async_database_url
from services.consentement import sign_consent
from services.photos_clinic import upload_photo

PATIENT_ID = 1
ACTE_ID = 1
CLINIC_ID = 1
ESTHETICIENNE_EMAIL = 'estheticienne.qa@autoclinique.test'

async def main():
    settings = get_settings()
    engine = create_async_engine(normalize_async_database_url(settings.database_url))
    Session = async_sessionmaker(engine, expire_on_commit=False)
    signature = 'data:image/png;base64,' + 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
    image_bytes = Path('/home/ubuntu/work/autoclinique/qa_photo_avant_fake.jpg').read_bytes()
    async with Session() as db:
        practitioner = await db.scalar(select(Utilisateur).where(
            Utilisateur.email == ESTHETICIENNE_EMAIL,
            Utilisateur.clinic_id == CLINIC_ID,
        ))
        if not practitioner:
            raise RuntimeError('Compte esthéticienne QA introuvable')
        existing_consent = await db.scalar(select(Consentement).where(
            Consentement.patient_id == PATIENT_ID,
            Consentement.clinic_id == CLINIC_ID,
            Consentement.acte_id == ACTE_ID,
            Consentement.methode_signature == 'qa_fake',
        ))
        if not existing_consent:
            consent = await sign_consent(
                patient_id=PATIENT_ID,
                acte_id=ACTE_ID,
                signature_b64=signature,
                method='qa_fake',
                ip_address='127.0.0.1',
                db=db,
                type_consentement='acte_medical',
                clinic_id=CLINIC_ID,
            )
            print(f'FAKE consent created id={consent.id}')
        else:
            print(f'FAKE consent already exists id={existing_consent.id}')
        existing_photo = await db.scalar(select(PhotoClinic).where(
            PhotoClinic.patient_id == PATIENT_ID,
            PhotoClinic.clinic_id == CLINIC_ID,
            PhotoClinic.type == 'avant',
            PhotoClinic.zone_anatomique == 'visage — QA FAKE',
        ))
        if not existing_photo:
            photo = await upload_photo(
                patient_id=PATIENT_ID,
                dossier_id=None,
                type_photo='avant',
                zone='visage — QA FAKE',
                angle='face-à-face',
                file_bytes=image_bytes,
                mime_type='image/jpeg',
                prise_par_id=practitioner.id,
                db=db,
                ip_address='127.0.0.1',
                user_agent='QA fake evidence seed',
                clinic_id=CLINIC_ID,
            )
            print(f'FAKE photo created id={photo.id}')
        else:
            print(f'FAKE photo already exists id={existing_photo.id}')
        await db.commit()
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(main())
