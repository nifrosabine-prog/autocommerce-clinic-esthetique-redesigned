"""AutoCommerce Clinic — API Settings (branding) & réservation publique"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
import re

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, limiter
from middleware.clinic_rbac import require_role
from models.database import RoleEnum, Utilisateur, UtilisateurActe, ActeMedical
from services.agenda import get_disponibilites
from services.branding import get_branding, update_branding, save_logo, save_hero, get_public_content
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


class EmailDeliverySettingsUpdate(BaseModel):
    """Identité d'envoi publique, sans jamais recevoir de clé API dans l'UI."""

    provider: str = Field(default="resend", pattern="^resend$")
    sending_domain: str = Field(..., min_length=3, max_length=253)
    from_email: str = Field(..., min_length=6, max_length=320)

    @field_validator("sending_domain")
    @classmethod
    def validate_sending_domain(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", normalized):
            raise ValueError("Le domaine d'envoi doit être un nom de domaine valide, sans chemin.")
        return normalized

    @field_validator("from_email")
    @classmethod
    def validate_from_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("L'adresse expéditrice est invalide.")
        return normalized

    @model_validator(mode="after")
    def validate_sender_matches_domain(self):
        if self.from_email.rsplit("@", 1)[-1] != self.sending_domain:
            raise ValueError("L'adresse expéditrice doit utiliser le domaine d'envoi configuré.")
        return self


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
    return await get_branding(db, clinic_id=_public_clinic_id())


@router.get("/settings/currency")
async def get_currency_route(db: AsyncSession = Depends(get_db), current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN))):
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


async def _email_delivery_response(db: AsyncSession, clinic_id: int) -> dict:
    from services.clinic_settings import get_setting

    configured = await get_setting("clinic.email_delivery", db, default={}, clinic_id=clinic_id)
    configured = configured if isinstance(configured, dict) else {}
    app_settings = get_settings()
    allowlisted = "email" in app_settings.allowed_external_integrations
    has_byok_secret = bool(app_settings.resend_api_key)
    from_email = configured.get("from_email")
    return {
        "provider": configured.get("provider", "resend"),
        "sending_domain": configured.get("sending_domain", ""),
        "from_email": from_email or "",
        "byok_secret_configured": has_byok_secret,
        "email_channel_allowed": allowlisted,
        "ready": bool(from_email and configured.get("sending_domain") and allowlisted and has_byok_secret),
        "secret_storage": "deployment_secret_only",
    }


@router.get("/settings/email-delivery")
async def get_email_delivery_settings(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    """Expose l'identité e-mail et l'état BYOK sans révéler la clé Resend."""
    return await _email_delivery_response(db, current_user["clinic_id"])


@router.put("/settings/email-delivery")
async def update_email_delivery_settings(
    payload: EmailDeliverySettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    from services.clinic_settings import set_setting

    await set_setting(
        "clinic.email_delivery",
        payload.model_dump(),
        description="Identité d'envoi BYOK de la clinique, sans clé API stockée en base",
        clinic_id=current_user["clinic_id"],
        db=db,
    )
    return await _email_delivery_response(db, current_user["clinic_id"])


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
    nom: str = Field(..., min_length=2, max_length=200)
    categorie: str = Field(..., min_length=2, max_length=50)
    duree_minutes: int = Field(..., ge=5, le=480)
    prix_base: Decimal = Field(..., ge=Decimal("0.000"), max_digits=10, decimal_places=3)
    is_gratuit: bool = False
    description: Optional[str] = None
    protocole: Optional[str] = None
    is_active: bool = True
    is_public: bool = False

    @field_validator("nom", "categorie")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Ce champ doit contenir au moins 2 caractères")
        return normalized

    @model_validator(mode="after")
    def validate_price_policy(self):
        if not self.is_gratuit and self.prix_base <= 0:
            raise ValueError("Un acte payant doit avoir un prix strictement supérieur à 0")
        return self


class ActeUpdate(BaseModel):
    nom: Optional[str] = Field(default=None, min_length=2, max_length=200)
    categorie: Optional[str] = Field(default=None, min_length=2, max_length=50)
    duree_minutes: Optional[int] = Field(default=None, ge=5, le=480)
    prix_base: Optional[Decimal] = Field(default=None, ge=Decimal("0.000"), max_digits=10, decimal_places=3)
    is_gratuit: Optional[bool] = None
    description: Optional[str] = None
    protocole: Optional[str] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None

    @field_validator("nom", "categorie")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Ce champ doit contenir au moins 2 caractères")
        return normalized

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


@router.get("/clinical/actes")
async def list_actes_cliniques_route(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE)),
):
    """Liste les actes internes actifs autorisés pour le praticien connecté."""
    result = await db.execute(
        select(ActeMedical)
        .join(UtilisateurActe, UtilisateurActe.acte_id == ActeMedical.id)
        .where(ActeMedical.clinic_id == current_user["clinic_id"])
        .where(ActeMedical.is_active)
        .where(UtilisateurActe.utilisateur_id == current_user["id"])
        .order_by(ActeMedical.categorie, ActeMedical.nom)
    )
    return result.scalars().all()

@router.post("/settings/actes", status_code=status.HTTP_201_CREATED)
async def create_acte_route(
    payload: ActeCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    normalized_name = payload.nom.casefold()
    existing = await db.execute(select(ActeMedical.id).where(
        ActeMedical.clinic_id == current_user["clinic_id"],
        ActeMedical.nom_normalise == normalized_name,
    ))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Un acte avec ce nom existe déjà dans la clinique")
    data = payload.model_dump()
    data["nom_normalise"] = normalized_name
    acte = ActeMedical(
        **data, clinic_id=current_user["clinic_id"],
    )
    db.add(acte)
    await db.flush()
    return acte

@router.patch("/settings/actes/{acte_id}")
async def update_acte_route(
    acte_id: int,
    payload: ActeUpdate,
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
    
    merged = {
        "nom": acte.nom,
        "categorie": acte.categorie,
        "duree_minutes": acte.duree_minutes,
        "prix_base": acte.prix_base,
        "is_gratuit": acte.is_gratuit,
        "description": acte.description,
        "protocole": acte.protocole,
        "is_active": acte.is_active,
        "is_public": acte.is_public,
    }
    merged.update(payload.model_dump(exclude_unset=True))
    validated = ActeCreate.model_validate(merged)
    normalized_name = validated.nom.casefold()
    duplicate = await db.execute(select(ActeMedical.id).where(
        ActeMedical.clinic_id == current_user["clinic_id"],
        ActeMedical.nom_normalise == normalized_name,
        ActeMedical.id != acte_id,
    ))
    if duplicate.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Un acte avec ce nom existe déjà dans la clinique")
    for field, value in validated.model_dump().items():
        setattr(acte, field, value)
    acte.nom_normalise = normalized_name
    
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
        .where(Utilisateur.is_public)
        .where(Utilisateur.role.in_([RoleEnum.MEDECIN.value, RoleEnum.ESTHETICIENNE.value]))
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
        .where(Utilisateur.is_public)
        .where(Utilisateur.role.in_([RoleEnum.MEDECIN.value, RoleEnum.ESTHETICIENNE.value]))
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
