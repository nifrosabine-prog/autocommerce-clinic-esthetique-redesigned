"""Passerelle publique de candidature — aucun compte clinique requis."""
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select

from api.deps import get_db
from config import get_settings
from models.database import Candidature, Poste, StatutPoste
from services.recrutement import create_candidature

router = APIRouter(prefix="/recrutement", tags=["public-recruitment"])
_ALLOWED_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_ALLOWED_SUFFIXES = {".pdf", ".doc", ".docx"}


def _public_clinic_id() -> int:
    settings = get_settings()
    if settings.env == "production" and not settings.public_routes_enabled:
        raise HTTPException(status_code=404, detail="Routes publiques désactivées pour ce déploiement")
    if not isinstance(settings.public_clinic_id, int) or settings.public_clinic_id <= 0:
        raise HTTPException(status_code=503, detail="Tenant public non configuré")
    return settings.public_clinic_id


def _extract_cv_text(content: bytes, suffix: str) -> str:
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader
            return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages).strip()
        if suffix == ".docx":
            from docx import Document
            return "\n".join(p.text for p in Document(BytesIO(content)).paragraphs).strip()
    except Exception:
        return ""
    return ""


@router.get("/postes")
async def public_open_posts():
    clinic_id = _public_clinic_id()
    async for db in get_db():
        rows = (await db.execute(
            select(Poste.id, Poste.titre, Poste.description)
            .where(Poste.clinic_id == clinic_id, Poste.statut == StatutPoste.OUVERT.value)
            .order_by(Poste.created_at.desc())
        )).all()
        return [{"id": row.id, "titre": row.titre, "description": row.description} for row in rows]


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def public_submit_application(
    poste_id: int = Form(...),
    nom_candidat: str = Form(..., min_length=2, max_length=160),
    email: str = Form(..., min_length=3, max_length=254),
    telephone: str | None = Form(None, max_length=40),
    cv: UploadFile | None = File(None),
):
    clinic_id = _public_clinic_id()
    async for db in get_db():
        poste = await db.scalar(select(Poste).where(
            Poste.id == poste_id, Poste.clinic_id == clinic_id, Poste.statut == StatutPoste.OUVERT.value
        ))
        if poste is None:
            raise HTTPException(status_code=400, detail="Poste ouvert introuvable")
        content = b""
        suffix = ""
        if cv is not None:
            suffix = Path(cv.filename or "").suffix.lower()
            if suffix not in _ALLOWED_SUFFIXES or cv.content_type not in _ALLOWED_TYPES:
                raise HTTPException(status_code=415, detail="Format accepté : PDF, DOC ou DOCX")
            content = await cv.read(10 * 1024 * 1024 + 1)
            if len(content) > 10 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Le CV ne doit pas dépasser 10 Mo")
        candidature = await create_candidature({
            "poste_id": poste_id,
            "poste": poste.titre,
            "nom_candidat": nom_candidat.strip(),
            "email": email.strip(),
            "telephone": telephone.strip() if telephone else None,
        }, db, clinic_id=clinic_id, created_by_id=None)
        if content:
            settings = get_settings()
            folder = Path(settings.uploads_dir) / "recrutement" / str(clinic_id) / str(candidature.id)
            folder.mkdir(parents=True, exist_ok=True)
            filename = f"{uuid4().hex}{suffix}"
            (folder / filename).write_bytes(content)
            candidature.cv_url = f"/api/v1/recrutement/{candidature.id}/documents/{filename}"
            candidature.cv_texte_extrait = (_extract_cv_text(content, suffix)[:12000] or None)
        await db.flush()
        return {"id": candidature.id, "statut": candidature.statut, "message": "Candidature reçue"}
    raise HTTPException(status_code=503, detail="Base de données indisponible")
