"""AutoCommerce Clinic — API Recrutement"""
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import Candidature, HistoriqueCandidature, RoleEnum
from config import get_settings

from services.recrutement import (
    analyser_cv_ia,
    changer_statut,
    create_candidature,
    create_poste,
    generer_annonce_ia,
    fermer_poste,
    list_candidatures,
    list_postes,
    extraire_texte_document,
)
from services.branding import get_branding_context
from config import WA_TEMPLATES

router = APIRouter(prefix="/recrutement", tags=["recrutement"])

RH_ROLES = (RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)
RH_LECTURE_ROLES = (RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)


class PosteCreate(BaseModel):
    titre: str
    description: Optional[str] = None


class AnalyseCvPayload(BaseModel):
    texte_cv: Optional[str] = None


class CandidatureCreate(BaseModel):
    poste: Optional[str] = None
    poste_id: Optional[int] = None
    nom_candidat: str
    email: str
    telephone: Optional[str] = None
    cv_url: Optional[str] = None
    lettre_url: Optional[str] = None


class StatutChange(BaseModel):
    statut: str
    notes_rh: Optional[str] = None
    date_entretien: Optional[datetime] = None


class CandidatureUpdate(BaseModel):
    notes_rh: Optional[str] = None
    date_entretien: Optional[datetime] = None


class DocumentType(BaseModel):
    type: str


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_candidature_route(
    payload: CandidatureCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    try:
        c = await create_candidature(
            payload.model_dump(), db, clinic_id=current_user["clinic_id"],
            created_by_id=current_user["id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # Notification WhatsApp à la directrice
    try:
        branding = await get_branding_context(db, clinic_id=current_user["clinic_id"])
        message = WA_TEMPLATES["candidature_recu"].format(
            poste=c.poste, nom=c.nom_candidat
        )
        message = f"{branding['clinic_name']} — {message}"
        from services.whatsapp_service import send_whatsapp_message
        from sqlalchemy import select as sa_select
        from models.database import Utilisateur as SAUtilisateur
        result = await db.execute(
            sa_select(SAUtilisateur.telephone)
            .where(SAUtilisateur.role == RoleEnum.DIRECTRICE.value)
            .where(SAUtilisateur.clinic_id == current_user["clinic_id"])
            .where(SAUtilisateur.is_active.is_(True))
            .limit(1)
        )
        phone = result.scalar_one_or_none()
        if phone:
            await send_whatsapp_message(phone, message)
    except Exception:
        pass  # La notification ne doit pas bloquer la création
    return {"id": c.id, "statut": c.statut}


@router.get("")
async def list_candidatures_route(
    statut: Optional[str] = Query(None),
    poste: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    candidatures = await list_candidatures(
        db, statut=statut, poste=poste,
        clinic_id=current_user["clinic_id"],
    )
    return [_serialize_candidature(c) for c in candidatures]


def _serialize_candidature(c: Candidature) -> dict:
    return {
        "id": c.id, "poste": c.poste, "poste_id": c.poste_id,
        "nom_candidat": c.nom_candidat, "email": c.email, "telephone": c.telephone,
        "cv_url": c.cv_url, "lettre_url": c.lettre_url, "statut": c.statut,
        "notes_rh": c.notes_rh, "date_entretien": c.date_entretien,
        "evaluateur_id": c.evaluateur_id, "analyse_ia_statut": c.analyse_ia_statut,
        "analyse_ia_resume": c.analyse_ia_resume, "analyse_ia_score": c.analyse_ia_score,
        "analyse_ia_le": c.analyse_ia_le, "created_at": c.created_at,
    }


@router.patch("/{candidature_id}/statut")
@router.put("/{candidature_id}/statut")
async def changer_statut_route(
    candidature_id: int,
    payload: StatutChange,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    try:
        c = await changer_statut(candidature_id, payload.statut, current_user["id"], db,
                                  notes_rh=payload.notes_rh, date_entretien=payload.date_entretien,
                                  clinic_id=current_user["clinic_id"])
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # Notification WhatsApp au candidat si changement de statut.
    # Correctif : la version précédente construisait le message puis ne
    # l'envoyait jamais (`if c.email: pass`). On envoie désormais réellement
    # au téléphone du candidat quand il est renseigné ; sinon on ne bloque
    # pas le changement de statut (la notification reste un bonus).
    try:
        branding = await get_branding_context(db, clinic_id=current_user["clinic_id"])
        message = WA_TEMPLATES["candidature_statut"].format(
            poste=c.poste, statut=c.statut
        )
        message = f"{branding['clinic_name']} — {message}"
        if c.telephone:
            from services.whatsapp_service import send_whatsapp_message
            await send_whatsapp_message(c.telephone, message)
    except Exception:
        pass  # La notification ne doit jamais bloquer le changement de statut
    return {"id": c.id, "statut": c.statut}


@router.get("/{candidature_id}/details")
async def get_candidature_route(
    candidature_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*RH_LECTURE_ROLES)),
):
    c = await db.scalar(select(Candidature).where(
        Candidature.id == candidature_id, Candidature.clinic_id == current_user["clinic_id"]
    ))
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidature non trouvée")
    return _serialize_candidature(c)


@router.get("/{candidature_id}/historique")
async def candidature_history_route(
    candidature_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*RH_LECTURE_ROLES)),
):
    c = await db.scalar(select(Candidature).where(
        Candidature.id == candidature_id, Candidature.clinic_id == current_user["clinic_id"]
    ))
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidature non trouvée")
    rows = (await db.execute(
        select(HistoriqueCandidature)
        .where(HistoriqueCandidature.candidature_id == candidature_id,
               HistoriqueCandidature.clinic_id == current_user["clinic_id"])
        .order_by(HistoriqueCandidature.changed_at.desc())
    )).scalars().all()
    return [{"id": h.id, "ancien_statut": h.ancien_statut,
             "nouveau_statut": h.nouveau_statut, "notes_rh": h.notes_rh,
             "date_entretien": h.date_entretien, "change_par_id": h.change_par_id,
             "changed_at": h.changed_at} for h in rows]


@router.patch("/{candidature_id}")
async def update_candidature_route(
    candidature_id: int, payload: CandidatureUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*RH_ROLES)),
):
    c = await db.scalar(select(Candidature).where(
        Candidature.id == candidature_id, Candidature.clinic_id == current_user["clinic_id"]
    ))
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidature non trouvée")
    if payload.notes_rh is not None:
        c.notes_rh = payload.notes_rh.strip() or None
    if payload.date_entretien is not None:
        c.date_entretien = payload.date_entretien
    await db.flush()
    return _serialize_candidature(c)


_ALLOWED_DOCUMENTS = {
    "cv": {"application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "lettre": {"application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
}
_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx"}


@router.post("/{candidature_id}/documents")
async def upload_candidature_document(
    candidature_id: int, type: str = Query(..., pattern="^(cv|lettre)$"),
    file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*RH_ROLES)),
):
    c = await db.scalar(select(Candidature).where(
        Candidature.id == candidature_id, Candidature.clinic_id == current_user["clinic_id"]
    ))
    if c is None:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _DOCUMENT_EXTENSIONS or file.content_type not in _ALLOWED_DOCUMENTS[type]:
        raise HTTPException(status_code=415, detail="Format accepté : PDF, DOC ou DOCX")
    max_bytes = 10 * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="Le document ne doit pas dépasser 10 Mo")
    settings = get_settings()
    folder = Path(settings.uploads_dir) / "recrutement" / str(current_user["clinic_id"]) / str(candidature_id)
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{suffix}"
    target = folder / filename
    target.write_bytes(content)
    relative_url = f"/api/v1/recrutement/{candidature_id}/documents/{filename}"
    if type == "cv":
        c.cv_url = relative_url
    else:
        c.lettre_url = relative_url
    await db.flush()
    return {"type": type, "url": relative_url, "filename": filename, "size": len(content)}


@router.get("/{candidature_id}/documents/{filename}")
async def download_candidature_document(
    candidature_id: int, filename: str, db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*RH_LECTURE_ROLES)),
):
    c = await db.scalar(select(Candidature).where(
        Candidature.id == candidature_id, Candidature.clinic_id == current_user["clinic_id"]
    ))
    if c is None:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")
    settings = get_settings()
    root = (Path(settings.uploads_dir) / "recrutement" / str(current_user["clinic_id"]) / str(candidature_id)).resolve()
    target = (root / Path(filename).name).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="Document non trouvé")
    return FileResponse(target, filename=target.name, media_type="application/octet-stream")


@router.post("/postes", status_code=status.HTTP_201_CREATED)
async def create_poste_route(
    payload: PosteCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*RH_ROLES)),
):
    p = await create_poste(
        payload.titre, payload.description, db,
        clinic_id=current_user["clinic_id"], cree_par_id=current_user["id"],
    )
    return {"id": p.id, "titre": p.titre, "statut": p.statut}


@router.get("/postes")
async def list_postes_route(
    statut: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*RH_LECTURE_ROLES)),
):
    postes = await list_postes(db, clinic_id=current_user["clinic_id"], statut=statut)
    return [
        {"id": p.id, "titre": p.titre, "description": p.description,
         "statut": p.statut, "created_at": p.created_at}
        for p in postes
    ]


@router.post("/postes/{poste_id}/fermer")
async def fermer_poste_route(
    poste_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*RH_ROLES)),
):
    try:
        p = await fermer_poste(poste_id, db, clinic_id=current_user["clinic_id"])
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"id": p.id, "statut": p.statut}


@router.post("/postes/{poste_id}/generer-annonce")
async def generer_annonce_route(
    poste_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*RH_ROLES)),
):
    try:
        texte = await generer_annonce_ia(poste_id, db, clinic_id=current_user["clinic_id"])
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return {"poste_id": poste_id, "texte": texte}


@router.post("/{candidature_id}/analyser-cv")
async def analyser_cv_route(
    candidature_id: int,
    payload: AnalyseCvPayload,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*RH_ROLES)),
):
    """Analyse IA optionnelle d'un CV.

    Ne renvoie jamais d'erreur bloquante : si le budget IA de la clinique
    est épuisé (ou l'IA désactivée), la réponse indique
    ``analyse_ia_statut = "indisponible"`` et le recrutement continue
    normalement à la main — aucune action manuelle n'est jamais empêchée
    par l'indisponibilité de l'IA.
    """
    if not payload.texte_cv:
        candidate = await db.scalar(select(Candidature).where(
            Candidature.id == candidature_id, Candidature.clinic_id == current_user["clinic_id"]
        ))
        if candidate and candidate.cv_texte_extrait:
            payload.texte_cv = candidate.cv_texte_extrait
        elif candidate and candidate.cv_url:
            settings = get_settings()
            filename = Path(candidate.cv_url).name
            root = (Path(settings.uploads_dir) / "recrutement" / str(current_user["clinic_id"]) / str(candidature_id)).resolve()
            target = (root / filename).resolve()
            if root in target.parents and target.is_file():
                payload.texte_cv = extraire_texte_document(target.read_bytes(), target.suffix)
    try:
        c = await analyser_cv_ia(
            candidature_id, db, clinic_id=current_user["clinic_id"],
            texte_cv=payload.texte_cv,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {
        "id": c.id,
        "analyse_ia_statut": c.analyse_ia_statut,
        "analyse_ia_resume": c.analyse_ia_resume,
        "analyse_ia_score": c.analyse_ia_score,
    }
