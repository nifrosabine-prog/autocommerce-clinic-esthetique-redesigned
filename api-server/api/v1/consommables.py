from typing import List, Optional, Literal
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from decimal import Decimal

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from services.consommables import ConsommableService
from services.stock_audit_pdf import generate_consommables_mouvements_pdf
from services.branding import get_branding_context

router = APIRouter(prefix="/consommables", tags=["consommables"])

# --- Schemas ---
class ConsommableBase(BaseModel):
    nom: str
    categorie: str
    unite: str
    seuil_alerte: Decimal = Decimal("0.00")
    stock_minimum: Decimal = Decimal("0.00")
    prix_unitaire: Decimal = Decimal("0.000")
    fournisseur_id: Optional[int] = None

class ConsommableCreate(ConsommableBase):
    stock_actuel: Decimal = Decimal("0.00")

class ConsommableUpdate(ConsommableBase):
    nom: Optional[str] = None
    categorie: Optional[str] = None
    unite: Optional[str] = None

class ConsommableResponse(ConsommableBase):
    id: int
    stock_actuel: Decimal
    is_active: bool

    class Config:
        from_attributes = True

class MouvementCreate(BaseModel):
    type: Literal["entree", "sortie", "ajustement"]
    quantite: float = Field(..., gt=0)
    motif: Optional[str] = None
    reference: Optional[str] = None

# --- Endpoints ---

@router.get("/list", response_model=List[ConsommableResponse])
async def list_consommables(
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE))
):
    return await ConsommableService.get_all(db)

@router.post("/create", response_model=ConsommableResponse, status_code=status.HTTP_201_CREATED)
async def create_consommable(
    data: ConsommableCreate,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE))
):
    return await ConsommableService.create(db, data.model_dump())

@router.put("/{consommable_id}", response_model=ConsommableResponse)
async def update_consommable(
    consommable_id: int,
    data: ConsommableUpdate,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE))
):
    updated = await ConsommableService.update(db, consommable_id, data.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Consommable non trouvé")
    return updated

@router.delete("/{consommable_id}")
async def delete_consommable(
    consommable_id: int,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE))
):
    success = await ConsommableService.delete(db, consommable_id)
    if not success:
        raise HTTPException(status_code=404, detail="Consommable non trouvé")
    return {"status": "success"}

@router.post("/{consommable_id}/mouvement")
async def add_mouvement(
    consommable_id: int,
    data: MouvementCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE))
):
    # Une entrée est une opération d’inventaire ; une sortie correspond à
    # l’attribution/consommation pendant un acte clinique.
    role = current_user.get("role") if isinstance(current_user, dict) else getattr(current_user, "role", None)
    gestionnaires = {RoleEnum.ADMIN.value, RoleEnum.DIRECTRICE.value, RoleEnum.ASSISTANTE.value}
    praticiens = {RoleEnum.ADMIN.value, RoleEnum.DIRECTRICE.value, RoleEnum.ASSISTANTE.value, RoleEnum.MEDECIN.value, RoleEnum.ESTHETICIENNE.value}
    # Un ajustement d'inventaire est une opération de gestion réservée.
    if data.type in ("entree", "ajustement") and role not in gestionnaires:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Opération non autorisée pour ce rôle")
    if data.type == "sortie" and role not in praticiens:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Opération non autorisée pour ce rôle")
    if data.type == "ajustement" and not data.motif:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Un motif est obligatoire pour un ajustement d'inventaire")
    try:
        mvt = await ConsommableService.add_mouvement(
            db,
            consommable_id,
            data.type,
            data.quantite,
            current_user["id"],
            data.motif,
            data.reference
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not mvt:
        raise HTTPException(status_code=404, detail="Consommable non trouvé")
    return {"status": "success", "mouvement_id": mvt.id}

@router.get("/alertes")
async def get_alertes(
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE))
):
    return await ConsommableService.get_alertes(db)


@router.get("/mouvements")
async def list_recent_mouvements(
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE))
):
    """Registre d'audit : derniers mouvements consommables."""
    return await ConsommableService.get_recent_mouvements(db)


@router.get("/mouvements/export-pdf")
async def export_consommables_mouvements_pdf(
    date_debut: Optional[str] = Query(None, description="Filtre : date début (YYYY-MM-DD)"),
    date_fin: Optional[str] = Query(None, description="Filtre : date fin (YYYY-MM-DD)"),
    consommable_id: Optional[int] = Query(None, ge=1, description="Filtre : consommable précis"),
    type_mouvement: Optional[str] = Query(
        None, pattern="^(entree|sortie|ajustement)$",
        description="Filtre : type de mouvement",
    ),
    limit: int = Query(2000, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Export PDF imprimable du registre des mouvements consommables (audit V2.3).

    Même RBAC que la réception / l'ajustement : réservé aux rôles
    gestionnaires (Admin, Directrice, Assistante).
    """
    clinic_id = current_user.get("clinic_id") or 1

    def _parse(v: Optional[str], nom: str):
        if not v:
            return None
        try:
            return date.fromisoformat(v)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"{nom} invalide (format YYYY-MM-DD attendu)")

    d_debut = _parse(date_debut, "date_debut")
    d_fin = _parse(date_fin, "date_fin")

    mouvements = await ConsommableService.get_mouvements_filtered(
        db,
        clinic_id=clinic_id,
        date_debut=d_debut,
        date_fin=d_fin,
        consommable_id=consommable_id,
        type_mvt=type_mouvement,
        limit=limit,
    )

    clinic = await get_branding_context(db, clinic_id=clinic_id)

    pdf_bytes = generate_consommables_mouvements_pdf(
        mouvements,
        clinic,
        filters={
            "date_debut": date_debut or None,
            "date_fin": date_fin or None,
            "consommable_id": consommable_id,
            "type": type_mouvement,
        },
    )
    filename = f"registre_mouvements_consommables_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{consommable_id}/mouvements")
async def list_consommable_mouvements(
    consommable_id: int,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE))
):
    """Historique des mouvements d'un consommable précis."""
    return await ConsommableService.get_mouvements(db, consommable_id)
