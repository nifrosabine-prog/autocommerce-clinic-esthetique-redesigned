"""Service commissions — toutes les opérations sont scoppées par clinique."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import COMMISSION_VALIDATION_SEUIL, get_settings
from models.database import Commission, StatutCommission, Utilisateur, Patient, Facture
from services.tenant_scope import resolve_clinic_id


async def create_commission(
    commercial_id: int,
    patient_id: int,
    facture_id: int,
    montant_ca: Decimal,
    db: AsyncSession,
    clinic_id: Optional[int] = None,
) -> Optional[Commission]:
    clinic_id = resolve_clinic_id(clinic_id)
    result = await db.execute(
        select(Utilisateur).where(
            Utilisateur.id == commercial_id,
            Utilisateur.clinic_id == clinic_id,
            Utilisateur.role == "commercial",
        )
    )
    commercial = result.scalar_one_or_none()
    if not commercial or commercial.taux_commission <= 0:
        return None

    patient = await db.scalar(select(Patient).where(
        Patient.id == patient_id,
        Patient.clinic_id == clinic_id,
    ))
    facture = await db.scalar(select(Facture).where(Facture.id == facture_id))
    if not patient:
        raise ValueError("Patient hors clinique")
    if facture is not None and facture.clinic_id != clinic_id:
        raise ValueError("Facture hors clinique")
    if facture is None and get_settings().env == "production":
        raise ValueError("Facture obligatoire en production")

    montant_commission = (
        montant_ca * commercial.taux_commission / Decimal("100")
    ).quantize(Decimal("0.001"))
    commission = Commission(
        clinic_id=clinic_id,
        commercial_id=commercial_id,
        patient_id=patient_id,
        facture_id=facture_id,
        montant_ca=montant_ca,
        taux_commission=commercial.taux_commission,
        montant_commission=montant_commission,
        statut=StatutCommission.EN_ATTENTE.value,
        periode_mois=date.today().replace(day=1),
    )
    db.add(commission)
    await db.flush()
    return commission


async def valider_commission(
    commission_id: int,
    validateur_id: int,
    db: AsyncSession,
    clinic_id: Optional[int] = None,
) -> Commission:
    clinic_id = resolve_clinic_id(clinic_id)
    commission = await db.scalar(select(Commission).where(
        Commission.id == commission_id,
        Commission.clinic_id == clinic_id,
    ))
    if not commission:
        raise ValueError("Commission non trouvée dans cette clinique")

    validateur = await db.scalar(select(Utilisateur).where(
        Utilisateur.id == validateur_id,
        Utilisateur.clinic_id == clinic_id,
        Utilisateur.is_active.is_(True),
    ))
    if not validateur and get_settings().env == "production":
        raise ValueError("Validateur non autorisé dans cette clinique")

    depasse_seuil = commission.montant_commission > Decimal(str(COMMISSION_VALIDATION_SEUIL))
    if commission.statut == StatutCommission.EN_ATTENTE.value:
        if depasse_seuil:
            commission.statut = StatutCommission.VALIDATION_PARTIELLE.value
            commission.validee_par_id = validateur_id
            commission.validated_at = datetime.utcnow()
        else:
            commission.statut = StatutCommission.VALIDEE.value
            commission.validee_par_id = validateur_id
            commission.validated_at = datetime.utcnow()
    elif commission.statut == StatutCommission.VALIDATION_PARTIELLE.value:
        if validateur_id == commission.validee_par_id:
            raise ValueError("La deuxième validation doit être faite par une personne différente")
        commission.statut = StatutCommission.VALIDEE.value
        commission.validee_par_id_2 = validateur_id
        commission.validated_at_2 = datetime.utcnow()
    else:
        raise ValueError(f"Statut invalide pour validation : {commission.statut}")

    await db.flush()
    return commission


async def marquer_payee(
    commission_id: int,
    date_paiement: date,
    db: AsyncSession,
    clinic_id: Optional[int] = None,
) -> Commission:
    clinic_id = resolve_clinic_id(clinic_id)
    commission = await db.scalar(select(Commission).where(
        Commission.id == commission_id,
        Commission.clinic_id == clinic_id,
    ))
    if not commission:
        raise ValueError("Commission non trouvée dans cette clinique")
    if commission.statut == StatutCommission.PAYEE.value:
        return commission
    if commission.statut != StatutCommission.VALIDEE.value:
        raise ValueError("La commission doit être validée avant paiement")
    commission.statut = StatutCommission.PAYEE.value
    commission.date_paiement = date_paiement
    await db.flush()
    return commission


async def list_commissions(
    current_user: dict,
    db: AsyncSession,
    periode_mois: Optional[date] = None,
    clinic_id: Optional[int] = None,
) -> list[Commission]:
    clinic_id = resolve_clinic_id(clinic_id or current_user.get("clinic_id"))
    query = select(Commission).where(Commission.clinic_id == clinic_id)
    if current_user.get("role") == "commercial":
        query = query.where(Commission.commercial_id == current_user.get("id"))
    if periode_mois:
        query = query.where(Commission.periode_mois == periode_mois)
    result = await db.execute(query.order_by(Commission.created_at.desc()))
    return list(result.scalars().all())


async def total_du_par_commercial(
    commercial_id: int,
    db: AsyncSession,
    clinic_id: Optional[int] = None,
) -> Decimal:
    clinic_id = resolve_clinic_id(clinic_id)
    result = await db.execute(select(Commission).where(
        Commission.commercial_id == commercial_id,
        Commission.clinic_id == clinic_id,
        Commission.statut != StatutCommission.PAYEE.value,
    ))
    commissions = result.scalars().all()
    return sum((c.montant_commission for c in commissions), Decimal("0.000"))


async def calculer_commissions_mois(
    commercial_id: int,
    periode_mois: date,
    db: AsyncSession,
    clinic_id: Optional[int] = None,
) -> int:
    """Crée les commissions manquantes sur les factures payées du mois.

    Le tenant est résolu depuis le commercial lorsque le job Celery ne reçoit
    pas explicitement de contexte. Une facture ne peut produire qu'une seule
    commission pour un commercial donné.
    """
    commercial = await db.scalar(select(Utilisateur).where(
        Utilisateur.id == commercial_id,
    ))
    if not commercial:
        return 0
    clinic_id = resolve_clinic_id(clinic_id or commercial.clinic_id)
    if commercial.clinic_id != clinic_id:
        raise ValueError("Commercial hors clinique")

    from calendar import monthrange
    first_day = periode_mois.replace(day=1)
    last_day = periode_mois.replace(day=monthrange(periode_mois.year, periode_mois.month)[1])
    result = await db.execute(
        select(Facture, Patient)
        .join(Patient, Facture.patient_id == Patient.id)
        .where(
            Facture.clinic_id == clinic_id,
            Patient.clinic_id == clinic_id,
            Patient.commercial_id == commercial_id,
            Facture.statut == "payee",
            Facture.date_emission >= first_day,
            Facture.date_emission <= last_day,
        )
    )
    created = 0
    for facture, patient in result.all():
        existing = await db.scalar(select(Commission).where(
            Commission.clinic_id == clinic_id,
            Commission.facture_id == facture.id,
            Commission.commercial_id == commercial_id,
        ))
        if existing:
            continue
        commission = await create_commission(
            commercial_id=commercial_id,
            patient_id=patient.id,
            facture_id=facture.id,
            montant_ca=facture.total_ttc,
            db=db,
            clinic_id=clinic_id,
        )
        if commission:
            created += 1
    await db.flush()
    return created
