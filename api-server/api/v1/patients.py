"""
AutoCommerce Clinic — API Patients

N'existait pas du tout : aucun moyen de créer un patient alors que
agenda/dossiers/factures en dépendent tous.
"""
from datetime import date
from io import StringIO
from typing import Optional
import csv

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from services.patients import (
    create_patient, get_patient, list_patients, update_patient, anonymize_patient,
    digits_only_phone,
)
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/patients", tags=["patients"])


class PatientCreate(BaseModel):
    nom: str
    prenom: str
    telephone: str
    date_naissance: Optional[date] = None
    genre: Optional[str] = None
    email: Optional[str] = None
    adresse: Optional[str] = None
    ville: Optional[str] = None
    groupe_sanguin: Optional[str] = None
    allergies: Optional[str] = None
    antecedents_medicaux: Optional[str] = None
    contre_indications: Optional[str] = None
    note_interne: Optional[str] = None
    source_acquisition: Optional[str] = None
    commercial_id: Optional[int] = None
    whatsapp_phone: Optional[str] = None
    consentement_marketing: bool = False


class PatientUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    date_naissance: Optional[date] = None
    genre: Optional[str] = None
    email: Optional[str] = None
    adresse: Optional[str] = None
    ville: Optional[str] = None
    groupe_sanguin: Optional[str] = None
    statut: Optional[str] = None
    allergies: Optional[str] = None
    antecedents_medicaux: Optional[str] = None
    contre_indications: Optional[str] = None
    note_interne: Optional[str] = None
    consentement_marketing: Optional[bool] = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_patient_route(
    payload: PatientCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
    )),
):
    try:
        return await create_patient(payload.model_dump(), db, current_user)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("")
async def list_patients_route(
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.COMMERCIAL, RoleEnum.ADMIN,
    )),
):
    return await list_patients(current_user, db, search=search, skip=skip, limit=limit)


@router.get("/export.csv")
async def export_patients_csv(
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.COMMERCIAL, RoleEnum.ADMIN,
    )),
):
    """Exporte les patients visibles par l’utilisateur dans un CSV non médical."""
    from sqlalchemy import or_, select
    from models.database import Patient
    from services.access_control import clinic_id_for

    query = select(Patient).where(
        Patient.anonymized_at.is_(None),
        Patient.clinic_id == clinic_id_for(current_user),
    )
    if current_user.get("role") == "commercial":
        query = query.where(Patient.commercial_id == current_user.get("id"))
    if search:
        like = f"%{search}%"
        conditions = [
            Patient.nom.ilike(like),
            Patient.prenom.ilike(like),
            Patient.telephone.ilike(like),
            Patient.whatsapp_phone.ilike(like),
        ]
        # Même normalisation téléphone que services/patients.py : l'export
        # CSV retrouve les patientes par chiffres seuls, quel que soit le
        # format saisi ou stocké (« +216 20 000 000 », « 20000000 », …).
        digits = "".join(char for char in search if char.isdigit())
        if digits:
            digits_like = f"%{digits}%"
            conditions.extend(
                digits_only_phone(column).ilike(digits_like)
                for column in (Patient.telephone, Patient.whatsapp_phone)
            )
        query = query.where(or_(*conditions))

    patients = (await db.execute(query.order_by(Patient.nom, Patient.prenom))).scalars().all()

    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow([
        "ID", "Nom", "Prénom", "Téléphone", "Email", "Date de naissance",
        "Genre", "Adresse", "Ville", "Statut", "Date d'inscription",
        "Dernière visite", "Points fidélité", "Niveau fidélité", "Commercial ID",
        "Consentement marketing",
    ])
    for patient in patients:
        writer.writerow([
            patient.id,
            patient.nom,
            patient.prenom,
            patient.telephone,
            patient.email or "",
            patient.date_naissance.isoformat() if patient.date_naissance else "",
            patient.genre or "",
            patient.adresse or "",
            patient.ville or "",
            patient.statut or "",
            patient.created_at.isoformat() if patient.created_at else "",
            patient.derniere_visite.isoformat() if patient.derniere_visite else "",
            patient.points_fidelite or 0,
            patient.niveau_fidelite or "",
            patient.commercial_id or "",
            "Oui" if patient.consentement_marketing else "Non",
        ])

    return StreamingResponse(
        iter(["\ufeff" + output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="patients.csv"'},
    )


@router.get("/{patient_id}")
async def get_patient_route(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.COMMERCIAL, RoleEnum.ADMIN,
    )),
):
    try:
        return await get_patient(patient_id, current_user, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.patch("/{patient_id}")
@router.put("/{patient_id}")
async def update_patient_route(
    patient_id: int,
    payload: PatientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
    )),
):
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        return await update_patient(patient_id, data, current_user, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.delete("/{patient_id}")
async def delete_patient_route(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    """Suppression logique (anonymisation) par défaut pour DELETE /{id}."""
    try:
        return await anonymize_patient(patient_id, db, current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{patient_id}/rgpd")
async def anonymize_patient_route(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    """Droit à l'oubli RGPD — réservé à la direction/admin, action irréversible."""
    try:
        return await anonymize_patient(patient_id, db, current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
