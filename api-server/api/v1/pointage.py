"""
AutoCommerce Clinic — API Pointage & RH
Gestion du temps de présence des praticiens.
"""

import io
from datetime import datetime, date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from api.deps import get_db
from middleware.auth import get_current_active_user
from middleware.clinic_rbac import require_role
from models.database import RoleEnum, Pointage, Utilisateur

router = APIRouter(prefix="/pointage", tags=["pointage"])

class PointageOut(BaseModel):
    id: int
    debut: datetime
    fin: Optional[datetime] = None
    duree_minutes: Optional[int] = None
    notes: Optional[str] = None

class PointageStatus(BaseModel):
    is_clocked_in: bool
    current_pointage: Optional[PointageOut] = None

class PointageReportItem(BaseModel):
    date: date
    debut: datetime
    fin: Optional[datetime]
    duree_minutes: int

class UserReport(BaseModel):
    utilisateur_id: int
    nom_complet: str
    total_minutes: int
    details: List[PointageReportItem]


def _format_duration(minutes: int) -> str:
    hours, remaining_minutes = divmod(minutes, 60)
    return f"{hours} h {remaining_minutes:02d} min"


def _render_attendance_pdf(report: UserReport, date_debut: date, date_fin: date) -> bytes:
    """Produit un export PDF administratif à partir du rapport déjà filtré par clinique."""
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Clinic Esthétique — Rapport de présence", styles["Title"]),
        Spacer(1, 0.35 * cm),
        Paragraph(f"Employé : <b>{report.nom_complet}</b>", styles["Normal"]),
        Paragraph(
            f"Période : du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}",
            styles["Normal"],
        ),
        Paragraph(f"Total : <b>{_format_duration(report.total_minutes)}</b>", styles["Normal"]),
        Spacer(1, 0.45 * cm),
    ]
    rows = [["Date", "Arrivée", "Départ", "Durée"]]
    for item in report.details:
        rows.append([
            item.date.strftime("%d/%m/%Y"),
            item.debut.strftime("%H:%M"),
            item.fin.strftime("%H:%M") if item.fin else "—",
            _format_duration(item.duree_minutes),
        ])
    if not report.details:
        rows.append(["Aucun pointage sur cette période.", "", "", ""])

    table = Table(rows, colWidths=[4.2 * cm, 3.4 * cm, 3.4 * cm, 4.2 * cm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    document.build(story)
    return buffer.getvalue()


async def _build_admin_report(
    utilisateur_id: int,
    date_debut: date,
    date_fin: date,
    clinic_id: int,
    db: AsyncSession,
) -> UserReport:
    if date_fin < date_debut:
        raise HTTPException(400, "La date de fin doit être postérieure ou égale à la date de début")

    target_user = await db.scalar(select(Utilisateur).where(
        Utilisateur.id == utilisateur_id,
        Utilisateur.clinic_id == clinic_id,
    ))
    if not target_user:
        raise HTTPException(404, "Utilisateur non trouvé dans votre clinique.")

    pointages = (await db.execute(
        select(Pointage)
        .where(
            Pointage.utilisateur_id == utilisateur_id,
            Pointage.clinic_id == clinic_id,
            Pointage.debut >= datetime.combine(date_debut, datetime.min.time()),
            Pointage.debut <= datetime.combine(date_fin, datetime.max.time()),
            Pointage.fin.is_not(None),
        )
        .order_by(Pointage.debut.asc())
    )).scalars().all()
    details = [
        PointageReportItem(
            date=pointage.debut.date(),
            debut=pointage.debut,
            fin=pointage.fin,
            duree_minutes=pointage.duree_minutes or 0,
        )
        for pointage in pointages
    ]
    return UserReport(
        utilisateur_id=utilisateur_id,
        nom_complet=f"{target_user.prenom} {target_user.nom}",
        total_minutes=sum(pointage.duree_minutes or 0 for pointage in pointages),
        details=details,
    )

@router.get("/statut", response_model=PointageStatus)
async def get_pointage_status(
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Vérifie si l'utilisateur est actuellement pointé (en cours)."""
    result = await db.execute(
        select(Pointage)
        .where(
            Pointage.utilisateur_id == current_user["id"],
            Pointage.clinic_id == current_user["clinic_id"],
            Pointage.fin.is_(None)
        )
        .order_by(Pointage.debut.desc())
    )
    current = result.scalar_one_or_none()
    
    return {
        "is_clocked_in": current is not None,
        "current_pointage": current
    }

@router.post("/entree", response_model=PointageOut)
async def clock_in(
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Marque l'arrivée du praticien."""
    # Vérifier s'il n'y a pas déjà un pointage en cours
    check = await db.execute(
        select(Pointage).where(
            Pointage.utilisateur_id == current_user["id"],
            Pointage.clinic_id == current_user["clinic_id"],
            Pointage.fin.is_(None),
        )
    )
    if check.scalar_one_or_none():
        raise HTTPException(400, "Vous êtes déjà pointé à l'arrivée.")

    new_p = Pointage(
        clinic_id=current_user["clinic_id"],
        utilisateur_id=current_user["id"],
        debut=datetime.utcnow()
    )
    db.add(new_p)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Un pointage est déjà ouvert pour cet utilisateur") from exc
    await db.refresh(new_p)
    return new_p

@router.post("/sortie", response_model=PointageOut)
async def clock_out(
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Marque le départ du praticien."""
    result = await db.execute(
        select(Pointage)
        .where(
            Pointage.utilisateur_id == current_user["id"],
            Pointage.clinic_id == current_user["clinic_id"],
            Pointage.fin.is_(None),
        )
        .order_by(Pointage.debut.desc())
    )
    current = result.scalar_one_or_none()
    
    if not current:
        raise HTTPException(400, "Aucun pointage en cours trouvé.")

    current.fin = datetime.utcnow()
    delta = current.fin - current.debut
    current.duree_minutes = int(delta.total_seconds() / 60)
    
    await db.commit()
    await db.refresh(current)
    return current

@router.get("/admin/synthese")
async def get_attendance_summary(
    utilisateur_id: int,
    current_user: dict = Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Retourne les heures réalisées aujourd’hui, cette semaine et ce mois."""
    clinic_id = current_user["clinic_id"]
    target = await db.scalar(select(Utilisateur).where(
        Utilisateur.id == utilisateur_id,
        Utilisateur.clinic_id == clinic_id,
    ))
    if not target:
        raise HTTPException(404, "Utilisateur non trouvé dans votre clinique.")

    now = datetime.utcnow()
    today_start = datetime.combine(now.date(), datetime.min.time())
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    rows = (await db.execute(select(Pointage).where(
        Pointage.utilisateur_id == utilisateur_id,
        Pointage.clinic_id == clinic_id,
        Pointage.fin.is_not(None),
        Pointage.debut >= month_start,
    ).order_by(Pointage.debut.desc()))).scalars().all()

    def minutes_since(start: datetime) -> int:
        return sum(row.duree_minutes or 0 for row in rows if row.debut >= start)

    return {
        "utilisateur_id": utilisateur_id,
        "nom_complet": f"{target.prenom} {target.nom}",
        "aujourd_hui_minutes": minutes_since(today_start),
        "semaine_minutes": minutes_since(week_start),
        "mois_minutes": minutes_since(month_start),
        "pointages_mois": len(rows),
    }


@router.get("/admin/rapport", response_model=UserReport)
async def get_admin_report(
    utilisateur_id: int,
    date_debut: date,
    date_fin: date,
    current_user: dict = Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Génère le rapport de présence pour un employé sur une période donnée."""
    return await _build_admin_report(
        utilisateur_id,
        date_debut,
        date_fin,
        current_user["clinic_id"],
        db,
    )


@router.get("/admin/rapport.pdf")
async def export_admin_report_pdf(
    utilisateur_id: int,
    date_debut: date,
    date_fin: date,
    current_user: dict = Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Exporte le rapport RH PDF uniquement pour la clinique et les rôles administratifs autorisés."""
    report = await _build_admin_report(
        utilisateur_id,
        date_debut,
        date_fin,
        current_user["clinic_id"],
        db,
    )
    filename = f"rapport-rh-{report.utilisateur_id}-{date_debut.isoformat()}-{date_fin.isoformat()}.pdf"
    return StreamingResponse(
        io.BytesIO(_render_attendance_pdf(report, date_debut, date_fin)),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
