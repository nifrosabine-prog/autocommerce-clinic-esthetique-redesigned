"""
AutoCommerce Clinic — API Dossiers Médicaux, Consentements, Photos
"""

import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import (
    DossierMedical, Consentement, Patient, PhotoClinic, RendezVous, ActeMedical,
)
from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum

from services.dossier_medical import create_dossier, get_timeline_patient, export_dossier_pdf
from services.consentement import preview_contract_consent, preview_contract_pdf, sign_consent
from services.photos_clinic import upload_photo, get_comparaison_avant_apres, delete_photo, get_decrypted_photo
from services.audit_medical import log_access
from services.clinic_settings import get_setting
from services.omnicanal.email_connector import EmailConnector
from config import get_settings

router = APIRouter(prefix="/patients", tags=["dossiers-medicaux"])
settings = get_settings()


# ── Schémas ────────────────────────────────────────────────

class DossierCreate(BaseModel):
    # Conservé pour compatibilité : l’API l’accepte uniquement quand il
    # désigne le praticien clinique authentifié.
    praticien_id: Optional[int] = None
    rdv_id: Optional[int] = None
    acte_id: Optional[int] = None
    date_acte: str  # ISO
    zones_traitees: Optional[dict] = None
    produits_utilises: Optional[dict] = None
    observations: Optional[str] = None
    effets_secondaires: Optional[str] = None
    satisfaction_patient: Optional[int] = Field(None, ge=1, le=5)
    suivi_requis: bool = False
    date_suivi_recommandee: Optional[str] = None
    actes_details: Optional[List[dict]] = None
    statut_clinique: str = Field(default="cloture", pattern="^(brouillon|cloture)$")


class ConsentementCreate(BaseModel):
    acte_id: Optional[int] = None
    acte_ids: List[int] = Field(default_factory=list, max_length=10)
    signature_base64: str = Field(min_length=1, max_length=1_000_000)
    signature_praticien_base64: Optional[str] = Field(default=None, min_length=1, max_length=1_000_000)
    methode_signature: str = "tactile"
    attestation_praticien: bool = False
    type_consentement: Optional[str] = Field(
        default=None,
        pattern="^(general|acte_medical|simulation_ia)$",
    )


class ConsentementContractPreviewRequest(BaseModel):
    acte_ids: List[int] = Field(min_length=1, max_length=10)


class ConsentementEmailSendRequest(BaseModel):
    confirmation: bool = Field(..., description="Confirmation explicite de l'envoi au patient")


# ── Dossiers ─────────────────────────────────────────────

@router.get("/{patient_id}/contexte-rendez-vous", response_model=List[dict])
async def get_patient_appointment_context(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE)),
):
    """Expose le contexte de rendez-vous récent/à venir du patient au praticien."""
    result = await db.execute(
        select(RendezVous, ActeMedical)
        .outerjoin(ActeMedical, RendezVous.acte_id == ActeMedical.id)
        .where(RendezVous.patient_id == patient_id, RendezVous.clinic_id == current_user["clinic_id"])
        .order_by(RendezVous.date_heure_debut.desc())
        .limit(8)
    )
    return [
        {
            "id": rdv.id,
            "acte_id": rdv.acte_id,
            "acte_nom": acte.nom if acte else "Consultation",
            "date_heure": rdv.date_heure_debut.isoformat(),
            "statut": rdv.statut,
        }
        for rdv, acte in result.all()
    ]

@router.post("/{patient_id}/dossiers", response_model=dict)
async def create_patient_dossier(
    patient_id: int,
    data: DossierCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE)),
):
    """Crée un dossier médical (vérifie consentement)."""
    if data.praticien_id is not None and data.praticien_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Un dossier médical doit être attribué au praticien clinique connecté.",
        )
    try:
        dossier = await create_dossier(
            patient_id=patient_id,
            praticien_id=current_user["id"],
            rdv_id=data.rdv_id,
            data={
                "acte_id": data.acte_id,
                "date_acte": datetime.fromisoformat(data.date_acte.replace("Z", "+00:00")).replace(tzinfo=None),
                "zones_traitees": data.zones_traitees,
                "produits_utilises": data.produits_utilises,
                "observations": data.observations,
                "effets_secondaires": data.effets_secondaires,
                "satisfaction_patient": data.satisfaction_patient,
                "suivi_requis": data.suivi_requis,
                "date_suivi_recommandee": datetime.strptime(data.date_suivi_recommandee, "%Y-%m-%d").date() if data.date_suivi_recommandee else None,
                "actes_details": data.actes_details,
                "statut_clinique": data.statut_clinique,
            },
            db=db,
            clinic_id=current_user["clinic_id"],
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return {
            "dossier_id": dossier.id,
            "statut_clinique": dossier.statut_clinique,
            "message": "Brouillon enregistré" if dossier.statut_clinique == "brouillon" else "Dossier clôturé avec succès",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{patient_id}/dossiers/{dossier_id}/cloturer", response_model=dict)
async def close_patient_dossier(
    patient_id: int,
    dossier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE)),
):
    """Clôture un brouillon après vérification du consentement spécifique."""
    from services.dossier_medical import close_dossier
    try:
        dossier = await close_dossier(
            patient_id=patient_id,
            dossier_id=dossier_id,
            praticien_id=current_user["id"],
            db=db,
            clinic_id=current_user["clinic_id"],
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return {"dossier_id": dossier.id, "statut_clinique": dossier.statut_clinique, "message": "Dossier clôturé"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{patient_id}/dossiers", response_model=List[dict])
async def get_patient_timeline(
    patient_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.DIRECTRICE)),
):
    """Timeline chronologique des dossiers."""
    return await get_timeline_patient(
        patient_id, db,
        utilisateur_id=current_user["id"],
        ip_address=request.client.host if request.client else None,
        user_role=current_user.get("role"),
        clinic_id=current_user["clinic_id"]
    )


@router.get("/{patient_id}/dossiers/{dossier_id}", response_model=dict)
async def get_dossier_detail(
    patient_id: int,
    dossier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.DIRECTRICE)),
):
    """Détail d'un dossier."""
    result = await db.execute(
        select(DossierMedical).where(
            DossierMedical.id == dossier_id,
            DossierMedical.patient_id == patient_id,
            DossierMedical.clinic_id == current_user["clinic_id"],
        )
    )
    dossier = result.scalar_one_or_none()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")

    await log_access(
        db=db, utilisateur_id=current_user["id"], patient_id=patient_id,
        action="READ_DOSSIER", resource_type="dossier", resource_id=dossier_id,
        ip_address=request.client.host if request.client else None,
    )

    from services.dossier_medical import decrypt_field
    role = current_user.get("role")
    
    return {
        "id": dossier.id,
        "date_acte": dossier.date_acte.isoformat(),
        "observations": decrypt_field(dossier.observations_enc) if (dossier.observations_enc and role != "directrice") else "[ACCÈS RÉSERVÉ]",
        "zones_traitees": dossier.zones_traitees,
        "produits_utilises": dossier.produits_utilises,
        "effets_secondaires": dossier.effets_secondaires if role != "directrice" else "[ACCÈS RÉSERVÉ]",
        "satisfaction": dossier.satisfaction_patient,
    }


@router.get("/{patient_id}/export-pdf")
async def export_patient_pdf(
    patient_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.DIRECTRICE)),
):
    """Export PDF complet du dossier patient."""
    await log_access(
        db=db, utilisateur_id=current_user["id"], patient_id=patient_id,
        action="EXPORT_PDF", resource_type="dossier_complet", resource_id=patient_id,
        ip_address=request.client.host if request.client else None,
    )
    from fastapi.responses import Response
    pdf_bytes = await export_dossier_pdf(
        patient_id, db,
        user_role=current_user.get("role"),
        clinic_id=current_user["clinic_id"]
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="dossier_patient_{patient_id}.pdf"'},
    )


# ── Consentements ─────────────────────────────────────────

@router.post("/{patient_id}/consentements/apercu-contrat", response_model=dict)
async def preview_consentement_contractuel(
    patient_id: int,
    data: ConsentementContractPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE)),
):
    """Prévisualise le contrat exact qui sera figé avant signature du patient."""
    try:
        return await preview_contract_consent(
            patient_id=patient_id,
            acte_ids=data.acte_ids,
            praticien_id=current_user["id"],
            clinic_id=current_user["clinic_id"],
            db=db,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/{patient_id}/consentements/apercu-contrat-pdf")
async def preview_consentement_contractuel_pdf(
    patient_id: int,
    data: ConsentementContractPreviewRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE)),
):
    """Télécharge l'aperçu contractuel non signé avant recueil des signatures."""
    try:
        pdf_bytes = await preview_contract_pdf(
            patient_id=patient_id,
            acte_ids=data.acte_ids,
            praticien_id=current_user["id"],
            clinic_id=current_user["clinic_id"],
            db=db,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    await log_access(
        db=db,
        utilisateur_id=current_user["id"],
        patient_id=patient_id,
        action="APERCU_CONTRAT_CONSENTEMENT_PDF",
        resource_type="consentement",
        resource_id=patient_id,
        ip_address=request.client.host if request.client else None,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="apercu-contrat-consentement-non-signe.pdf"'},
    )


@router.post("/{patient_id}/consentements", response_model=dict)
async def create_consentement(
    patient_id: int,
    data: ConsentementCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE)),
):
    """Signe un consentement."""
    try:
        consent = await sign_consent(
            patient_id=patient_id,
            acte_id=data.acte_id,
            signature_b64=data.signature_base64,
            method=data.methode_signature,
            ip_address=request.client.host if request.client else None,
            db=db,
            type_consentement=data.type_consentement,
            clinic_id=current_user["clinic_id"],
            acte_ids=data.acte_ids or None,
            praticien_id=current_user["id"] if (data.type_consentement or "acte_medical") == "acte_medical" else None,
            attestation_praticien=data.attestation_praticien,
            signature_praticien_b64=data.signature_praticien_base64,
        )
        return {
            "consentement_id": consent.id,
            "type_consentement": consent.type_consentement,
            "est_valide": consent.est_valide,
            "signe_le": consent.signe_le.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{patient_id}/consentements/{consentement_id}/export-pdf")
async def export_consentement_contractuel_pdf(
    patient_id: int,
    consentement_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.DIRECTRICE)),
):
    """Télécharge le PDF archivé d'un consentement de la clinique courante."""
    consentement = await db.scalar(select(Consentement).where(
        Consentement.id == consentement_id,
        Consentement.patient_id == patient_id,
        Consentement.clinic_id == current_user["clinic_id"],
    ))
    if not consentement:
        raise HTTPException(status_code=404, detail="Consentement introuvable")
    path = f"{settings.data_dir}/uploads/consentement_{consentement.id}.pdf"
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="PDF de consentement indisponible")
    await log_access(
        db=db,
        utilisateur_id=current_user["id"],
        patient_id=patient_id,
        action="EXPORT_CONSENTEMENT_PDF",
        resource_type="consentement",
        resource_id=consentement_id,
        ip_address=request.client.host if request.client else None,
    )
    with open(path, "rb") as consent_file:
        pdf_bytes = consent_file.read()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="contrat-consentement-{consentement.id}.pdf"'},
    )


@router.post("/{patient_id}/consentements/{consentement_id}/envoyer-email", response_model=dict)
async def email_consentement_contractuel_pdf(
    patient_id: int,
    consentement_id: int,
    data: ConsentementEmailSendRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.DIRECTRICE)),
):
    """Envoie le PDF déjà signé après confirmation explicite du praticien."""
    if not data.confirmation:
        raise HTTPException(status_code=400, detail="Confirmez explicitement l'envoi au patient.")
    consentement = await db.scalar(select(Consentement).where(
        Consentement.id == consentement_id,
        Consentement.patient_id == patient_id,
        Consentement.clinic_id == current_user["clinic_id"],
        Consentement.est_valide,
    ))
    if not consentement or not consentement.contrat_snapshot:
        raise HTTPException(status_code=404, detail="Contrat signé introuvable")
    patient = await db.scalar(select(Patient).where(
        Patient.id == patient_id,
        Patient.clinic_id == current_user["clinic_id"],
    ))
    if not patient or not patient.email:
        raise HTTPException(status_code=422, detail="L'adresse e-mail du patient est manquante.")
    email_delivery = await get_setting(
        "clinic.email_delivery", db, default={}, clinic_id=current_user["clinic_id"]
    )
    if not isinstance(email_delivery, dict) or email_delivery.get("provider") != "resend":
        raise HTTPException(status_code=409, detail="Identité e-mail BYOK non configurée dans Paramètres.")
    from_email = email_delivery.get("from_email")
    sending_domain = email_delivery.get("sending_domain")
    if not isinstance(from_email, str) or not isinstance(sending_domain, str) or from_email.rsplit("@", 1)[-1].lower() != sending_domain.lower():
        raise HTTPException(status_code=409, detail="L'identité e-mail de la clinique est invalide.")
    if "email" not in settings.allowed_external_integrations or not settings.resend_api_key:
        raise HTTPException(status_code=409, detail="Canal e-mail BYOK non activé : configurez la clé de déploiement et autorisez le canal e-mail.")
    pdf_path = f"{settings.data_dir}/uploads/consentement_{consentement.id}.pdf"
    if not os.path.isfile(pdf_path):
        raise HTTPException(status_code=404, detail="PDF de consentement indisponible")
    with open(pdf_path, "rb") as consent_file:
        pdf_bytes = consent_file.read()
    result = await EmailConnector().send_media(
        patient.email,
        media_type="document",
        media_bytes=pdf_bytes,
        from_address=from_email,
        filename=f"contrat-consentement-{consentement.id}.pdf",
        caption="Votre contrat de consentement signé — document confidentiel",
    )
    if not result.get("success"):
        detail = result.get("details") or "Échec de l'envoi du contrat"
        raise HTTPException(status_code=502, detail=str(detail))
    await log_access(
        db=db,
        utilisateur_id=current_user["id"],
        patient_id=patient_id,
        action="ENVOI_CONTRAT_CONSENTEMENT_EMAIL",
        resource_type="consentement",
        resource_id=consentement_id,
        ip_address=request.client.host if request.client else None,
    )
    return {
        "status": "sent",
        "recipient": patient.email,
        "external_message_id": result.get("external_message_id"),
    }


@router.get("/{patient_id}/consentements", response_model=List[dict])
async def list_consentements(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.DIRECTRICE)),
):
    """Liste les consentements d'un patient."""
    result = await db.execute(
        select(Consentement)
        .where(
            Consentement.patient_id == patient_id,
            Consentement.clinic_id == current_user["clinic_id"],
        )
        .order_by(Consentement.signe_le.desc())
    )
    consentements = result.scalars().all()
    return [
        {
            "id": c.id,
            "type": c.type_consentement,
            "acte_id": c.acte_id,
            "signe_le": c.signe_le.isoformat(),
            "methode": c.methode_signature,
            "est_valide": c.est_valide,
            "est_contractuel": bool(c.contrat_snapshot),
            "actes": (c.contrat_snapshot or {}).get("actes", []),
            "praticien": (c.contrat_snapshot or {}).get("praticien", {}).get("nom_complet"),
        }
        for c in consentements
    ]


# ── Photos ─────────────────────────────────────────────────

@router.post("/{patient_id}/photos", response_model=dict)
async def upload_patient_photo(
    patient_id: int,
    request: Request,
    dossier_id: Optional[int] = Query(None),
    type_photo: str = Query(..., pattern="^(avant|apres|progression|complication|autre)$"),
    zone: Optional[str] = Query(None),
    angle: Optional[str] = Query(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE)),
):
    """Upload une photo médicale."""
    try:
        max_bytes = settings.max_photo_size_mb * 1024 * 1024
        file_bytes = await file.read(max_bytes + 1)
        if len(file_bytes) > max_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Fichier photo trop volumineux")
        photo = await upload_photo(
            patient_id=patient_id,
            dossier_id=dossier_id,
            type_photo=type_photo,
            zone=zone,
            angle=angle,
            file_bytes=file_bytes,
            mime_type=file.content_type or "image/jpeg",
            prise_par_id=current_user["id"],
            db=db,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            clinic_id=current_user["clinic_id"],
        )
        return {
            "photo_id": photo.id,
            "url": f"/api/v1/patients/{patient_id}/photos/{photo.id}/view",
            "thumbnail": f"/api/v1/patients/{patient_id}/photos/{photo.id}/view?thumbnail=true",
            "hash": photo.hash_fichier,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{patient_id}/photos", response_model=List[dict])
async def list_photos(
    patient_id: int,
    zone: Optional[str] = Query(None),
    type_photo: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE)),
):
    """Liste les photos d'un patient."""
    from sqlalchemy import and_
    query = select(PhotoClinic).where(
        and_(
            PhotoClinic.patient_id == patient_id,
            PhotoClinic.clinic_id == current_user["clinic_id"],
            ~PhotoClinic.is_deleted,
        )
    )
    if zone:
        query = query.where(PhotoClinic.zone_anatomique == zone)
    if type_photo:
        query = query.where(PhotoClinic.type == type_photo)

    query = query.order_by(PhotoClinic.date_prise.desc())
    result = await db.execute(query)
    photos = result.scalars().all()

    return [
        {
            "id": p.id,
            "type": p.type,
            "zone": p.zone_anatomique,
            "date": p.date_prise.isoformat(),
            "thumbnail": f"/api/v1/patients/{patient_id}/photos/{p.id}/view?thumbnail=true",
            "visible_patient": p.visible_patient,
            "visible_marketing": p.visible_marketing,
        }
        for p in photos
    ]


@router.get("/{patient_id}/photos/avant-apres")
async def get_avant_apres(
    patient_id: int,
    request: Request,
    zone: Optional[str] = Query(None),
    serie_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE)),
):
    """Photos avant/après pour comparaison."""
    return await get_comparaison_avant_apres(
        patient_id, zone, serie_id, db,
        utilisateur_id=current_user["id"],
        ip_address=request.client.host if request.client else None,
        clinic_id=current_user["clinic_id"],
    )


@router.get("/{patient_id}/photos/{photo_id}/view")
async def view_photo(
    patient_id: int,
    photo_id: int,
    request: Request,
    thumbnail: bool = Query(False),
    db: AsyncSession = Depends(get_db),
        current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE)),
):
    """Déchiffre et retourne une photo médicale (JPEG).
 Sans cette route,
    le frontend n'a aucun moyen d'afficher les photos avant/après."""
    try:
        content, filename = await get_decrypted_photo(
            photo_id, patient_id, db, thumbnail=thumbnail,
            clinic_id=current_user["clinic_id"],
            utilisateur_id=current_user["id"],
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return Response(
        content=content,
        media_type="image/jpeg",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{patient_id}/photos/{photo_id}")
async def soft_delete_photo(
    patient_id: int,
    photo_id: int,
    request: Request,
    raison: str = Query(..., min_length=5),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN)),
):
    """Soft delete d'une photo (jamais suppression physique)."""
    try:
        photo = await delete_photo(
            photo_id=photo_id,
            patient_id=patient_id,
            raison=raison,
            deleted_by=current_user["id"],
            db=db,
            clinic_id=current_user["clinic_id"],
            ip_address=request.client.host if request.client else None,
        )
        return {
            "photo_id": photo.id,
            "is_deleted": photo.is_deleted,
            "deleted_at": photo.deleted_at.isoformat() if photo.deleted_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
