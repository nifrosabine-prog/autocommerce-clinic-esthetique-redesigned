"""AutoCommerce Clinic — API Settings (branding) & réservation publique"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, limiter
from middleware.clinic_rbac import require_role
from models.database import RoleEnum, Utilisateur, ActeMedical
from services.agenda import get_disponibilites
from services.branding import get_branding, sanitize_public_branding, update_branding, save_logo, save_hero, get_public_content
from services.booking_requests import submit_booking_request
from config import get_settings

router = APIRouter(tags=["private-settings"])
public_router = APIRouter(tags=["public-gateway"])


def _public_clinic_id() -> int:
    settings = get_settings()
    if settings.env == "production" and not settings.public_routes_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Routes publiques désactivées pour ce déploiement",
        )
    clinic_id = settings.public_clinic_id
    if not isinstance(clinic_id, int) or clinic_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tenant public non configuré",
        )
    return clinic_id


class ContenuLanding(BaseModel):
    titre: Optional[str] = None
    sous_titre: Optional[str] = None
    services_mis_en_avant: Optional[list[str]] = None
    adresse: Optional[str] = None
    ville: Optional[str] = None
    telephone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None
    photo_hero_url: Optional[str] = None
    description_longue: Optional[str] = None
    horaires: Optional[str] = None


class BrandingUpdate(BaseModel):
    nom_clinique: Optional[str] = None
    couleur_primaire: Optional[str] = None
    couleur_secondaire: Optional[str] = None
    contenu_landing: Optional[ContenuLanding] = None


class GlobalCurrencyUpdate(BaseModel):
    currency_code: str = Field(..., min_length=3, max_length=3)
    currency_symbol: str = Field(..., min_length=1, max_length=8)


class ReservationPublique(BaseModel):
    nom: str
    prenom: str
    telephone: str
    email: Optional[str] = None
    praticien_id: Optional[int] = None
    specialite: Optional[str] = None
    acte_id: int
    date_heure: datetime


# ── Branding ───────────────────────────────────────────────

@router.get("/settings/branding")
async def get_branding_route(db: AsyncSession = Depends(get_db)):
    """Public — lu par la landing page avec tenant explicitement configuré."""
    return sanitize_public_branding(await get_branding(db, clinic_id=_public_clinic_id()))


@router.get("/settings/currency")
async def get_currency_route(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.COMMERCIAL, RoleEnum.ADMIN,
    )),
):
    from services.clinic_settings import get_setting
    currency = await get_setting("clinic.currency", db, clinic_id=current_user["clinic_id"])
    if not currency:
        currency = {"currency_code": "TND", "currency_symbol": "DT"}
    return currency


@router.put("/settings/currency")
async def update_currency_route(
    payload: GlobalCurrencyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    from services.clinic_settings import set_setting
    await set_setting(
        "clinic.currency",
        payload.model_dump(),
        db,
        description="Devise globale de la clinique",
        clinic_id=current_user["clinic_id"],
    )
    return {"status": "success", "currency": payload.model_dump()}


@router.patch("/settings/branding")
async def update_branding_route(
    payload: BrandingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    data = payload.model_dump(exclude_none=True)
    return await update_branding(
        data, db, clinic_id=current_user["clinic_id"],
    )


@router.post("/settings/branding/logo")
async def upload_logo_route(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    file_bytes = await file.read()
    try:
        logo_url = save_logo(
            file_bytes, file.content_type,
            clinic_id=current_user["clinic_id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    updated = await update_branding(
        {"logo_url": logo_url}, db,
        clinic_id=current_user["clinic_id"],
    )
    return {"logo_url": updated["logo_url"]}


@router.post("/settings/branding/hero")
async def upload_hero_route(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    file_bytes = await file.read()
    try:
        hero_url = save_hero(file_bytes, file.content_type, clinic_id=current_user["clinic_id"])
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    updated = await update_branding({"contenu_landing": {"photo_hero_url": hero_url}}, db, clinic_id=current_user["clinic_id"])
    return {"photo_hero_url": updated["contenu_landing"]["photo_hero_url"]}


# ── Gestion des Actes (Admin) ──────────────────────────────

class ActeCreate(BaseModel):
    nom: str
    categorie: str
    duree_minutes: int = 30
    prix_base: Decimal = Decimal("0.000")
    description: Optional[str] = None
    protocole: Optional[str] = None
    # Les actes créés dans le catalogue clinique doivent être disponibles
    # pour la réservation et la sélection par les rôles autorisés.
    is_active: bool = True
    is_public: bool = True

class GlobalCurrencyUpdate(BaseModel):
    currency_code: str
    currency_symbol: str

@router.get("/settings/actes")
async def list_actes_admin_route(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    result = await db.execute(select(ActeMedical)
        .where(ActeMedical.clinic_id == current_user["clinic_id"])
        .order_by(ActeMedical.nom))
    return result.scalars().all()

@router.post("/settings/actes", status_code=status.HTTP_201_CREATED)
async def create_acte_route(
    payload: ActeCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    acte = ActeMedical(
        **payload.model_dump(), clinic_id=current_user["clinic_id"],
    )
    db.add(acte)
    await db.flush()
    return acte

@router.patch("/settings/actes/{acte_id}")
async def update_acte_route(
    acte_id: int,
    payload: ActeCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    result = await db.execute(select(ActeMedical).where(
        ActeMedical.id == acte_id,
        ActeMedical.clinic_id == current_user["clinic_id"],
    ))
    acte = result.scalar_one_or_none()
    if not acte:
        raise HTTPException(status_code=404, detail="Acte non trouvé")
    
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(acte, field, value)
    
    await db.flush()
    return acte

# ── Réservation publique ───────────────────────────────────

@public_router.get("/content")
async def public_content_route(db: AsyncSession = Depends(get_db)):
    """Contenu dynamique consolidé pour la landing page (branding, expertises, IA)."""
    return await get_public_content(db, clinic_id=_public_clinic_id())


@public_router.get("/praticiens")
async def public_praticiens_route(db: AsyncSession = Depends(get_db)):
    """Liste publique des praticiens réservable depuis la landing page."""
    clinic_id = _public_clinic_id()
    result = await db.execute(
        select(Utilisateur)
        .where(Utilisateur.clinic_id == clinic_id)
        .where(Utilisateur.is_active)
        .where(Utilisateur.role.in_([RoleEnum.MEDECIN.value, RoleEnum.ESTHETICIENNE.value]))
        .where(Utilisateur.is_public)
        .order_by(Utilisateur.prenom, Utilisateur.nom)
    )
    praticiens = result.scalars().all()
    return [
        {
            "id": praticien.id,
            "nom": praticien.nom,
            "prenom": praticien.prenom,
            "nom_complet": f"{praticien.prenom} {praticien.nom}",
            "specialite": praticien.specialite,
            "agenda_color": praticien.agenda_color,
        }
        for praticien in praticiens
    ]


@public_router.get("/actes")
async def public_actes_route(db: AsyncSession = Depends(get_db)):
    """Catalogue public des actes activés."""
    clinic_id = _public_clinic_id()
    result = await db.execute(
        select(ActeMedical)
        .where(ActeMedical.clinic_id == clinic_id)
        .where(ActeMedical.is_active)
        .where(ActeMedical.is_public)
        .order_by(ActeMedical.nom)
    )
    actes = result.scalars().all()
    return [
        {
            "id": acte.id,
            "nom": acte.nom,
            "categorie": acte.categorie,
            "duree_minutes": acte.duree_minutes,
            "description": acte.description,
            "prix_base": float(acte.prix_base) if acte.prix_base is not None else None,
        }
        for acte in actes
    ]


@public_router.get("/disponibilites/{praticien_id}")
async def public_disponibilites_route(
    praticien_id: int,
    date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    acte_id: Optional[int] = Query(None),
    duree: Optional[int] = Query(None, ge=15, le=240),
    db: AsyncSession = Depends(get_db),
):
    """Créneaux libres publics d'un praticien pour un jour donné."""
    clinic_id = _public_clinic_id()
    praticien_result = await db.execute(
        select(Utilisateur)
        .where(Utilisateur.id == praticien_id)
        .where(Utilisateur.clinic_id == clinic_id)
        .where(Utilisateur.is_active)
        .where(Utilisateur.role.in_([RoleEnum.MEDECIN.value, RoleEnum.ESTHETICIENNE.value]))
        .where(Utilisateur.is_public)
    )
    praticien = praticien_result.scalar_one_or_none()
    if not praticien:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Praticien non trouvé")

    if date:
        try:
            date_jour = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Date invalide (format YYYY-MM-DD)")
    else:
        date_jour = datetime.utcnow().date()

    duree_minutes = duree or 30
    if acte_id is not None:
        acte_result = await db.execute(
            select(ActeMedical)
            .where(ActeMedical.id == acte_id)
            .where(ActeMedical.clinic_id == clinic_id)
            .where(ActeMedical.is_active)
            .where(ActeMedical.is_public)
        )
        acte = acte_result.scalar_one_or_none()
        if not acte:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acte non trouvé")
        duree_minutes = acte.duree_minutes

    creneaux = await get_disponibilites(
        praticien_id, date_jour, duree_minutes, db, clinic_id=clinic_id
    )

    if date_jour == datetime.utcnow().date():
        now = datetime.utcnow()
        creneaux = [
            creneau for creneau in creneaux
            if datetime.fromisoformat(creneau["datetime"]) >= now
        ]

    return {
        "praticien_id": praticien_id,
        "date": date_jour.isoformat(),
        "duree_minutes": duree_minutes,
        "creneaux": creneaux,
    }


class CallbackLeadCreate(BaseModel):
    nom: str
    telephone: str
    email: Optional[str] = None
    message: Optional[str] = None


@public_router.post("/rappel", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def callback_lead_route(request: Request, payload: CallbackLeadCreate, db: AsyncSession = Depends(get_db)):
    from models.database import CallbackLead
    nom = payload.nom.strip()
    telephone = payload.telephone.strip()
    if len(nom) < 2 or len(telephone) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nom et téléphone requis")
    lead = CallbackLead(clinic_id=_public_clinic_id(), nom=nom[:100], telephone=telephone[:30], email=(payload.email or None), message=(payload.message or None))
    db.add(lead)
    await db.flush()
    return {"lead_id": lead.id, "statut": lead.statut, "message": "Votre demande de rappel a bien été reçue."}


@router.get("/callback-leads")
async def list_callback_leads_route(
    statut: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN, RoleEnum.COMMERCIAL)),
):
    from models.database import CallbackLead
    query = select(CallbackLead).where(CallbackLead.clinic_id == current_user["clinic_id"])
    if statut:
        query = query.where(CallbackLead.statut == statut)
    query = query.order_by(CallbackLead.created_at.desc()).limit(100)
    result = await db.execute(query)
    return result.scalars().all()


@router.patch("/callback-leads/{lead_id}")
async def update_callback_lead_route(
    lead_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN, RoleEnum.COMMERCIAL)),
):
    from models.database import CallbackLead
    lead = await db.scalar(select(CallbackLead).where(CallbackLead.id == lead_id, CallbackLead.clinic_id == current_user["clinic_id"]))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead introuvable")
    if payload.get("statut") in {"pending", "contacted", "closed", "rejected"}:
        lead.statut = payload["statut"]
        if lead.statut == "contacted":
            lead.contacted_at = datetime.utcnow()
    if "notes" in payload:
        lead.notes = str(payload["notes"] or "")[:2000] or None
    await db.flush()
    return lead


@public_router.post("/reservation", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def reservation_publique_route(
    request: Request,
    payload: ReservationPublique,
    db: AsyncSession = Depends(get_db),
):
    """Public — crée une BookingRequest, jamais un Appointment direct.

    La validation par un utilisateur du Private Clinical Core est obligatoire
    avant toute création de patient clinique ou de rendez-vous interne.
    """
    try:
        result = await submit_booking_request(
            payload.model_dump(), db, clinic_id=_public_clinic_id()
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return result
