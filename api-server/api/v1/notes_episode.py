"""Collaboration d'épisode : notes privées et résumé partagé."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from api.deps import get_db
from middleware.auth import get_current_active_user
from models.episode_core import EpisodePatient, NotePrivee, NotePartagee
from services.access_control import clinic_id_for
from services.dossier_medical import encrypt_field, decrypt_field
from services.rbac_service import role_of, filter_private_notes

router = APIRouter(prefix="/episodes", tags=["episode-notes"])
PRIVATE_READ = {"medecin", "directrice", "estheticienne", "prestataire"}
SHARED_ROLES = PRIVATE_READ | {"assistante", "admin"}
class NoteCreate(BaseModel):
    contenu: str = Field(min_length=1, max_length=10000)
    intervention_id: int | None = None

async def episode(db, episode_id, user):
    item = await db.scalar(select(EpisodePatient).where(EpisodePatient.id == episode_id, EpisodePatient.clinic_id == clinic_id_for(user)))
    if not item: raise HTTPException(404, "Épisode introuvable")
    return item

def shared_payload(item): return {"id": item.id, "episode_id": item.episode_id, "auteur_id": item.auteur_id, "contenu": item.contenu, "created_at": item.created_at.isoformat(), "archived_at": item.archived_at.isoformat() if item.archived_at else None}

def private_payload(item):
    try: content = decrypt_field(item.contenu_enc)
    except Exception: content = "[note protégée indisponible]"
    return {"id": item.id, "episode_id": item.episode_id, "intervention_id": item.intervention_id, "auteur_id": item.auteur_id, "contenu": content, "created_at": item.created_at.isoformat(), "archived_at": item.archived_at.isoformat() if item.archived_at else None}

@router.post("/{episode_id}/notes-privees", status_code=201)
async def create_private(episode_id: int, data: NoteCreate, current_user=Depends(get_current_active_user), db: AsyncSession=Depends(get_db)):
    if role_of(current_user) not in PRIVATE_READ: raise HTTPException(403, "Ce rôle ne peut pas créer une note privée")
    await episode(db, episode_id, current_user)
    item = NotePrivee(clinic_id=clinic_id_for(current_user), episode_id=episode_id, intervention_id=data.intervention_id, auteur_id=int(current_user["id"]), contenu_enc=encrypt_field(data.contenu))
    db.add(item); await db.commit(); return private_payload(item)

@router.get("/{episode_id}/notes-privees")
async def list_private(episode_id: int, current_user=Depends(get_current_active_user), db: AsyncSession=Depends(get_db)):
    if role_of(current_user) not in PRIVATE_READ: return []
    await episode(db, episode_id, current_user)
    query = select(NotePrivee).where(NotePrivee.episode_id == episode_id, NotePrivee.clinic_id == clinic_id_for(current_user), NotePrivee.archived_at.is_(None))
    rows = list((await db.execute(query.order_by(NotePrivee.created_at.desc()))).scalars().all())
    return [private_payload(item) for item in filter_private_notes(current_user, rows)]

@router.post("/{episode_id}/notes-partagees", status_code=201)
async def create_shared(episode_id: int, data: NoteCreate, current_user=Depends(get_current_active_user), db: AsyncSession=Depends(get_db)):
    if role_of(current_user) not in SHARED_ROLES: raise HTTPException(403, "Ce rôle ne peut pas publier un résumé partagé")
    await episode(db, episode_id, current_user)
    item = NotePartagee(clinic_id=clinic_id_for(current_user), episode_id=episode_id, auteur_id=int(current_user["id"]), contenu=data.contenu)
    db.add(item); await db.commit(); return shared_payload(item)

@router.get("/{episode_id}/notes-partagees")
async def list_shared(episode_id: int, current_user=Depends(get_current_active_user), db: AsyncSession=Depends(get_db)):
    if role_of(current_user) not in SHARED_ROLES: raise HTTPException(403, "Accès refusé")
    await episode(db, episode_id, current_user)
    rows = (await db.execute(select(NotePartagee).where(NotePartagee.episode_id == episode_id, NotePartagee.clinic_id == clinic_id_for(current_user), NotePartagee.archived_at.is_(None)).order_by(NotePartagee.created_at.desc()))).scalars().all()
    return [shared_payload(item) for item in rows]

@router.post("/notes-privees/{note_id}/archive")
async def archive_private(note_id: int, current_user=Depends(get_current_active_user), db: AsyncSession=Depends(get_db)):
    item = await db.scalar(select(NotePrivee).where(NotePrivee.id == note_id, NotePrivee.clinic_id == clinic_id_for(current_user), NotePrivee.archived_at.is_(None)))
    if not item: raise HTTPException(404, "Note introuvable")
    if role_of(current_user) not in {"directrice", "admin"} and item.auteur_id != int(current_user["id"]): raise HTTPException(403, "Seul l'auteur ou la direction peut archiver cette note")
    item.archived_at = datetime.utcnow(); item.archived_by_id = int(current_user["id"]); await db.commit(); return {"id": item.id, "archived": True}
