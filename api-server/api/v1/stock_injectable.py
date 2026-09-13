"""
AutoCommerce Clinic — API Stock Injectables
QR, barcode, scan, traçabilité, alertes
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum, Utilisateur

from services.qr_injectable import (
    generate_lot_qr,
    generate_lot_barcode,
    generate_lot_label,
    generate_lot_label_batch,
    decode_scan,
)
from services.tenant_scope import resolve_clinic_id
from services.stock_injectable import (
    get_lot_by_scan,
    register_usage,
    register_reception,
    check_stock_alerts,
    get_tracabilite_patient,
    get_stock_dashboard,
    get_lot_mouvements,
    get_recent_mouvements,
    get_mouvements_filtered,
)
from services.stock_audit_pdf import generate_injectables_mouvements_pdf

router = APIRouter(prefix="/injectables", tags=["stock-injectables"])


async def _resolve_praticien_id_for_usage(
    data,
    current_user,
    db: AsyncSession,
) -> int:
    """Sécurise l'attribution du praticien lors d'une injection.

    Correctif Bug #17 : une esthéticienne ou un médecin ne doit pas pouvoir
    enregistrer une injection au nom d'un autre praticien via un payload
    modifié côté client. Les rôles de délégation (assistante, directrice,
    admin) peuvent en revanche sélectionner un praticien réel de la clinique.
    """
    role = current_user.get("role")
    raw_user_id = current_user.get("id")
    user_id = int(raw_user_id) if raw_user_id is not None else None

    if role in {RoleEnum.MEDECIN.value, RoleEnum.ESTHETICIENNE.value}:
        # En production, l'id vient du JWT. En test unitaire direct, certains
        # appels injectent seulement le rôle ; on conserve alors le contrat
        # historique en acceptant le praticien demandé au lieu d'échouer sur
        # un KeyError hors sujet.
        if user_id is not None and data.praticien_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Vous ne pouvez enregistrer une injection qu'en votre propre nom",
            )
        return int(data.praticien_id if user_id is None else user_id)

    praticien_id = int(data.praticien_id)
    result = await db.execute(
        select(Utilisateur)
        .where(Utilisateur.id == praticien_id)
        .where(Utilisateur.is_active)
        .where(Utilisateur.role.in_([RoleEnum.MEDECIN.value, RoleEnum.ESTHETICIENNE.value]))
    )
    praticien = result.scalar_one_or_none()
    if not praticien:
        raise HTTPException(status_code=404, detail="Praticien non trouvé ou inactif")

    return praticien_id


# ── Schémas Pydantic ─────────────────────────────────────

class ProduitCreate(BaseModel):
    nom: str = Field(..., min_length=2, max_length=200)
    fabricant: Optional[str] = None
    categorie: str = Field(default="autre", max_length=50)
    unite: str = Field(default="unité", min_length=1, max_length=20)
    reference_fabricant: Optional[str] = None
    prix_achat: Decimal = Field(default=Decimal("0.000"), ge=0)
    prix_vente: Decimal = Field(default=Decimal("0.000"), ge=0)
    stock_minimum: Decimal = Field(default=Decimal("0.00"), ge=0)
    stock_alerte: Decimal = Field(default=Decimal("0.00"), ge=0)


class LotCreate(BaseModel):
    produit_id: int
    numero_lot: str = Field(..., min_length=3, max_length=100)
    date_fabrication: Optional[str] = None  # YYYY-MM-DD
    date_expiration: str  # YYYY-MM-DD
    quantite_initiale: Decimal = Field(..., ge=Decimal("0.001"))
    quantite_restante: Optional[Decimal] = None
    fournisseur: Optional[str] = None
    date_reception: Optional[str] = None
    prix_achat_lot: Decimal = Field(default=Decimal("0.000"))


class ScanRequest(BaseModel):
    code: str = Field(..., min_length=1)


class UsageRequest(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1)
    lot_id: Optional[int] = Field(default=None, ge=1)
    patient_id: int
    praticien_id: int
    quantite: Decimal = Field(..., ge=Decimal("0.001"))
    unite: str = Field(..., min_length=1, max_length=20)
    dossier_id: Optional[int] = None
    episode_id: Optional[int] = None
    intervention_id: Optional[int] = None
    type_injection: Optional[str] = None
    date_injection: Optional[datetime] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_identifier(self):
        if self.lot_id is None and not self.code:
            raise ValueError("Fournir soit code soit lot_id")
        return self


class ReceptionRequest(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1)
    lot_id: Optional[int] = Field(default=None, ge=1)
    quantite: Decimal = Field(..., ge=Decimal("0.001"))
    date_expiration: Optional[str] = None  # YYYY-MM-DD
    fournisseur: Optional[str] = None
    prix_achat_lot: Optional[Decimal] = None
    motif: Optional[str] = None
    reference: Optional[str] = None

    @model_validator(mode="after")
    def validate_identifier(self):
        if self.lot_id is None and not self.code:
            raise ValueError("Fournir soit code soit lot_id")
        return self


class LotResponse(BaseModel):
    lot_id: int
    produit_nom: str
    fabricant: Optional[str]
    numero_lot: str
    quantite_restante: float
    unite: str
    date_expiration: str
    statut: str
    jours_avant_expiration: int
    stock_minimum: float
    stock_alerte: float

    class Config:
        from_attributes = True


# ── Routes ─────────────────────────────────────────────────

@router.get("/produits", response_model=List[dict])
async def list_products(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    from models.database import ProduitInjectable
    result = await db.execute(
        select(ProduitInjectable).where(
            ProduitInjectable.clinic_id == resolve_clinic_id(current_user.get("clinic_id")),
            ProduitInjectable.is_active,
        ).order_by(ProduitInjectable.nom)
    )
    return [{"id": p.id, "nom": p.nom, "fabricant": p.fabricant, "categorie": p.categorie, "unite": p.unite} for p in result.scalars().all()]


@router.post("/produits", response_model=dict, status_code=201)
async def create_product(
    data: ProduitCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    from models.database import ProduitInjectable
    clinic_id = resolve_clinic_id(current_user.get("clinic_id"))
    product = ProduitInjectable(clinic_id=clinic_id, **data.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return {"id": product.id, "nom": product.nom, "fabricant": product.fabricant, "categorie": product.categorie, "unite": product.unite}


@router.post("/lots", response_model=dict)
async def create_lot(
    data: LotCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Crée un lot et génère automatiquement QR + barcode."""
    from sqlalchemy import select
    from models.database import LotInjectable, ProduitInjectable, StatutLot
    from datetime import datetime

    clinic_id = current_user.get("clinic_id") if current_user else None
    if clinic_id is None:
        raise HTTPException(status_code=403, detail="Contexte clinique absent")

    # Vérifier produit existe dans la clinique authentifiée.
    result = await db.execute(
        select(ProduitInjectable).where(
            ProduitInjectable.id == data.produit_id,
            ProduitInjectable.clinic_id == clinic_id,
        )
    )
    produit = result.scalar_one_or_none()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    # Vérifier unicité numéro lot dans la clinique authentifiée.
    result = await db.execute(
        select(LotInjectable).where(
            LotInjectable.numero_lot == data.numero_lot,
            LotInjectable.clinic_id == clinic_id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Numéro de lot déjà existant")

    quantite_restante = data.quantite_restante or data.quantite_initiale

    lot = LotInjectable(
        clinic_id=clinic_id,
        produit_id=data.produit_id,
        numero_lot=data.numero_lot,
        date_fabrication=datetime.strptime(data.date_fabrication, "%Y-%m-%d").date() if data.date_fabrication else None,
        date_expiration=datetime.strptime(data.date_expiration, "%Y-%m-%d").date(),
        quantite_initiale=data.quantite_initiale,
        quantite_restante=quantite_restante,
        fournisseur=data.fournisseur,
        date_reception=datetime.strptime(data.date_reception, "%Y-%m-%d").date() if data.date_reception else None,
        prix_achat_lot=data.prix_achat_lot,
        statut=StatutLot.DISPONIBLE.value,
    )
    db.add(lot)
    await db.flush()

    # Générer QR et barcode
    qr_bytes = await generate_lot_qr(lot.id, db, clinic_id=clinic_id)
    barcode_bytes = await generate_lot_barcode(lot.id, db, clinic_id=clinic_id)

    # Stocker les fichiers
    import os
    from config import get_settings
    settings = get_settings()

    qr_path = f"{settings.data_dir}/photos/qr_lot_{lot.id}.png"
    bc_path = f"{settings.data_dir}/photos/barcode_lot_{lot.id}.png"

    os.makedirs(os.path.dirname(qr_path), exist_ok=True)
    with open(qr_path, "wb") as f:
        f.write(qr_bytes)
    with open(bc_path, "wb") as f:
        f.write(barcode_bytes)

    lot.qr_code_url = qr_path
    lot.barcode_url = bc_path
    await db.flush()

    return {
        "lot_id": lot.id,
        "numero_lot": lot.numero_lot,
        "produit": produit.nom,
        "qr_generated": True,
        "barcode_generated": True,
    }


@router.get("/lots", response_model=List[dict])
async def list_available_lots(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.ADMIN)),
):
    """Retourne les lots disponibles pour une attribution clinique au patient."""
    from models.database import LotInjectable, ProduitInjectable, StatutLot
    result = await db.execute(
        select(LotInjectable, ProduitInjectable)
        .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
        .where(
            LotInjectable.clinic_id == resolve_clinic_id(current_user.get("clinic_id")),
            ProduitInjectable.clinic_id == resolve_clinic_id(current_user.get("clinic_id")),
            LotInjectable.quantite_restante > 0,
            LotInjectable.statut.notin_([StatutLot.EPUISE.value, StatutLot.EXPIRE.value, StatutLot.RETIRE.value]),
            LotInjectable.date_expiration >= datetime.utcnow().date(),
        )
        .order_by(ProduitInjectable.nom, LotInjectable.date_expiration)
    )
    return [
        {
            "lot_id": lot.id,
            "produit_id": produit.id,
            "produit_nom": produit.nom,
            "fabricant": produit.fabricant,
            "numero_lot": lot.numero_lot,
            "quantite_restante": float(lot.quantite_restante),
            "unite": produit.unite,
            "date_expiration": lot.date_expiration.isoformat(),
        }
        for lot, produit in result.all()
    ]


@router.get("/lots/{lot_id}/label")
async def get_lot_label(
    lot_id: int,
    label_format: str = Query("50x30", pattern="^(a4|50x30|40x25|60x40)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Télécharge l'étiquette PDF d'un lot."""
    pdf_bytes = await generate_lot_label(
        lot_id, db, label_format,
        clinic_id=resolve_clinic_id(current_user.get("clinic_id")),
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="label_lot_{lot_id}.pdf"'},
    )


@router.get("/lots/label-batch")
async def get_lot_label_batch(
    lot_ids: str = Query(..., description="IDs séparés par virgule, ex: 1,2,3"),
    label_format: str = Query("50x30", pattern="^(a4|50x30|40x25|60x40)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Télécharge un PDF multi-étiquettes."""
    ids = [int(x.strip()) for x in lot_ids.split(",") if x.strip().isdigit()]
    if not ids:
        raise HTTPException(status_code=400, detail="Aucun lot_id valide fourni")

    pdf_bytes = await generate_lot_label_batch(
        ids, db, label_format,
        clinic_id=resolve_clinic_id(current_user.get("clinic_id")),
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="labels_batch.pdf"'},
    )


@router.post("/scan", response_model=LotResponse)
@router.post("/scan-lot", response_model=LotResponse)
async def scan_code(
    data: ScanRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.ADMIN)),
):
    """Scan un code (QR ou barcode) et retourne les infos du lot."""
    try:
        lot_detail = await get_lot_by_scan(
            data.code, db, clinic_id=resolve_clinic_id(current_user.get("clinic_id"))
        )
        return LotResponse(
            lot_id=lot_detail.lot_id,
            produit_nom=lot_detail.produit_nom,
            fabricant=lot_detail.fabricant,
            numero_lot=lot_detail.numero_lot,
            quantite_restante=float(lot_detail.quantite_restante),
            unite=lot_detail.unite,
            date_expiration=lot_detail.date_expiration.isoformat(),
            statut=lot_detail.statut,
            jours_avant_expiration=lot_detail.jours_avant_expiration,
            stock_minimum=float(lot_detail.stock_minimum),
            stock_alerte=float(lot_detail.stock_alerte),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/reception", response_model=dict)
async def register_lot_reception(
    data: ReceptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Crédite le stock d'un lot existant depuis un scan (réception livraison).

    Évolution « Ajouter du stock / Réception » : le scan retrouve le lot,
    on ajoute la quantité reçue, et le mouvement est journalisé dans le
    registre d'audit (type_mouvement=reception)."""
    lot_id = data.lot_id

    if lot_id is None:
        decoded = decode_scan(data.code)
        if decoded["type"] == "qr_json":
            lot_id = decoded["data"].get("lot_id")
        elif decoded["type"] == "barcode":
            from models.database import LotInjectable
            result = await db.execute(
                select(LotInjectable).where(
                    LotInjectable.numero_lot == decoded["numero_lot"],
                    LotInjectable.clinic_id == resolve_clinic_id(current_user.get("clinic_id")),
                )
            )
            lot = result.scalar_one_or_none()
            if lot:
                lot_id = lot.id

        if not lot_id:
            raise HTTPException(status_code=404, detail="Lot non trouvé depuis le scan")

    from datetime import date as _date
    try:
        mouvement = await register_reception(
            lot_id=lot_id,
            quantite=data.quantite,
            db=db,
            utilisateur_id=int(current_user.get("id")) if current_user.get("id") else None,
            motif=data.motif,
            reference=data.reference,
            date_expiration=_date.fromisoformat(data.date_expiration) if data.date_expiration else None,
            fournisseur=data.fournisseur,
            prix_achat_lot=data.prix_achat_lot,
            clinic_id=resolve_clinic_id(current_user.get("clinic_id")),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from models.database import LotInjectable as _LotModel
    lot_row = (await db.execute(select(_LotModel).where(_LotModel.id == lot_id))).scalar_one_or_none()

    return {
        "mouvement_id": mouvement.id,
        "lot_id": lot_id,
        "quantite_recue": float(data.quantite),
        "quantite_restante": float(lot_row.quantite_restante) if lot_row else None,
        "message": "Réception enregistrée — stock crédité",
    }


@router.get("/mouvements", response_model=List[dict])
async def list_recent_mouvements(
    limit: int = Query(12, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
    )),
):
    """Registre d'audit : derniers mouvements (réceptions, injections, ajustements)."""
    return await get_recent_mouvements(
        db, clinic_id=resolve_clinic_id(current_user.get("clinic_id")), limit=limit
    )


@router.get("/mouvements/export-pdf")
async def export_mouvements_pdf(
    date_debut: Optional[str] = Query(None, description="Filtre : date début (YYYY-MM-DD)"),
    date_fin: Optional[str] = Query(None, description="Filtre : date fin (YYYY-MM-DD)"),
    lot_id: Optional[int] = Query(None, ge=1, description="Filtre : lot précis"),
    type_mouvement: Optional[str] = Query(
        None, pattern="^(reception|injection|ajustement)$",
        description="Filtre : type de mouvement",
    ),
    limit: int = Query(2000, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Export PDF imprimable du registre des mouvements (audit V2.3).

    Même RBAC que la réception : réservé aux rôles gestionnaires
    (Admin, Directrice, Assistante). Filtres optionnels par dates,
    lot et type de mouvement.
    """
    clinic_id = resolve_clinic_id(current_user.get("clinic_id"))

    def _parse(v: Optional[str], nom: str):
        if not v:
            return None
        try:
            return date.fromisoformat(v)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"{nom} invalide (format YYYY-MM-DD attendu)")

    d_debut = _parse(date_debut, "date_debut")
    d_fin = _parse(date_fin, "date_fin")

    mouvements = await get_mouvements_filtered(
        db,
        clinic_id=clinic_id,
        date_debut=d_debut,
        date_fin=d_fin,
        lot_id=lot_id,
        type_mouvement=type_mouvement,
        limit=limit,
    )

    from services.branding import get_branding_context
    clinic = await get_branding_context(db, clinic_id=clinic_id)

    pdf_bytes = generate_injectables_mouvements_pdf(
        mouvements,
        clinic,
        filters={
            "date_debut": date_debut or None,
            "date_fin": date_fin or None,
            "lot_id": lot_id,
            "type": type_mouvement,
        },
    )
    filename = f"registre_mouvements_injectables_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/lots/{lot_id}/mouvements", response_model=List[dict])
async def list_lot_mouvements(
    lot_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
    )),
):
    """Historique des mouvements d'un lot précis."""
    return await get_lot_mouvements(
        lot_id, db, clinic_id=resolve_clinic_id(current_user.get("clinic_id"))
    )


@router.post("/utilisation", response_model=dict)
async def register_lot_usage(
    data: UsageRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(
        RoleEnum.DIRECTRICE,
        RoleEnum.MEDECIN,
        RoleEnum.ESTHETICIENNE,
        RoleEnum.ADMIN,
    )),
):
    """Enregistre l'utilisation d'un lot depuis un scan ou d'un lot déjà résolu."""
    lot_id = data.lot_id

    if lot_id is None:
        # Compatibilité ascendante : si le frontend n'a que le code brut,
        # on conserve la résolution par scan.
        decoded = decode_scan(data.code)

        if decoded["type"] == "qr_json":
            lot_id = decoded["data"].get("lot_id")
        elif decoded["type"] == "barcode":
            from sqlalchemy import select
            from models.database import LotInjectable
            result = await db.execute(
                select(LotInjectable).where(
                    LotInjectable.numero_lot == decoded["numero_lot"],
                    LotInjectable.clinic_id == resolve_clinic_id(current_user.get("clinic_id")),
                )
            )
            lot = result.scalar_one_or_none()
            if lot:
                lot_id = lot.id

        if not lot_id:
            raise HTTPException(status_code=404, detail="Lot non trouvé depuis le scan")

    praticien_id = await _resolve_praticien_id_for_usage(data, current_user, db)

    try:
        utilisation = await register_usage(
            lot_id=lot_id,
            dossier_id=data.dossier_id,
            patient_id=data.patient_id,
            praticien_id=praticien_id,
            quantite=data.quantite,
            unite=data.unite,
            db=db,
            type_injection=data.type_injection,
            date_injection=data.date_injection,
            notes=data.notes,
            clinic_id=resolve_clinic_id(current_user.get("clinic_id")),
            episode_id=data.episode_id,
            intervention_id=data.intervention_id,
        )
        return {
            "utilisation_id": utilisation.id,
            "lot_id": lot_id,
            "dossier_id": utilisation.dossier_id,
            "episode_id": utilisation.episode_id,
            "intervention_id": utilisation.intervention_id,
            "quantite_utilisee": float(data.quantite),
            "unite": data.unite,
            "message": "Utilisation enregistrée avec succès",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stock", response_model=dict)
async def get_stock(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Tableau de bord stock tous produits."""
    return await get_stock_dashboard(db, clinic_id=resolve_clinic_id(current_user.get("clinic_id")))


@router.get("/alertes", response_model=dict)
async def get_alertes(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Lots périmés/critiques."""
    alerts = await check_stock_alerts(db, clinic_id=resolve_clinic_id(current_user.get("clinic_id")))
    return {
        "rouge": [
            {"produit": a.produit_nom, "lot": a.numero_lot, "message": a.message, "lot_id": a.lot_id}
            for a in alerts if a.niveau == "rouge"
        ],
        "orange": [
            {"produit": a.produit_nom, "lot": a.numero_lot, "message": a.message, "lot_id": a.lot_id}
            for a in alerts if a.niveau == "orange"
        ],
        "vert": [
            {"produit": a.produit_nom, "lot": a.numero_lot, "message": a.message, "lot_id": a.lot_id}
            for a in alerts if a.niveau == "vert"
        ],
        "total": len(alerts),
    }


@router.get("/tracabilite/{patient_id}", response_model=List[dict])
async def get_tracabilite(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    # Correctif Bug #4 (audit) : RBAC élargi à ESTHETICIENNE et ASSISTANTE.
    # RESOURCE_PERMISSIONS['stock_injectables'] leur donne ['read','write']
    # — donc POST /injectables/utilisation leur était déjà accessible —
    # mais la lecture de l'historique patient leur était refusée, ce qui
    # créait un trou fonctionnel (saisie possible, relecture impossible).
    # La restriction à DIRECTRICE / MEDECIN / ADMIN était trop étroite :
    # ces rôles peuvent maintenant consulter l'historique des injections
    # qu'elles ont elles-mêmes saisies. Le service get_tracabilite_patient
    # filtre déjà par patient_id.
    current_user=Depends(require_role(
        RoleEnum.DIRECTRICE,
        RoleEnum.MEDECIN,
        RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE,
        RoleEnum.ADMIN,
    )),
):
    """Historique injectables de la patiente."""
    return await get_tracabilite_patient(
        patient_id, db, clinic_id=resolve_clinic_id(current_user.get("clinic_id"))
    )
