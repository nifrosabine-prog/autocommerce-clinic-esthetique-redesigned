"""
AutoCommerce Clinic — Service Factures

Calcul des totaux (jamais de float pour les montants — Decimal
partout, cf. règle absolue du projet), numérotation séquentielle
par année, et déclenchement automatique de la commission commerciale
+ des points de fidélité au moment du paiement.
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError

from models.database import DossierMedical, Facture, Patient, StatutFacture
from config import get_settings
from services.commissions import create_commission
from services.fidelite import add_points
from services.clinic_settings import get_setting

# 1 point de fidélité par tranche de 10 (unité monétaire) dépensée
POINTS_PAR_UNITE = Decimal("10")


async def _generate_numero_facture(db) -> str:
    annee = date.today().year
    result = await db.execute(
        select(func.count(Facture.id)).where(
            Facture.numero_facture.like(f"F-{annee}-%")
        )
    )
    count = result.scalar_one()
    return f"F-{annee}-{count + 1:04d}"


def _json_lines(lines: list[dict] | None) -> list[dict]:
    """Convertit les montants Decimal en valeurs JSON sérialisables."""
    return [
        {
            **line,
            "prix": str(Decimal(str(line["prix"]))),
            "quantite": int(line.get("quantite", 1)),
        }
        for line in (lines or [])
    ]


def _compute_totals(actes: list[dict], produits: list[dict], remise_globale_pct: Decimal,
                     taux_tva: Decimal) -> dict:
    if remise_globale_pct < Decimal("0") or remise_globale_pct > Decimal("100"):
        raise ValueError("La remise doit être comprise entre 0 et 100 %")
    if taux_tva < Decimal("0") or taux_tva > Decimal("1"):
        raise ValueError("Le taux de TVA doit être compris entre 0 et 1")
    lignes = (actes or []) + (produits or [])
    for line in lignes:
        prix = Decimal(str(line.get("prix", "0")))
        quantite = Decimal(str(line.get("quantite", "1")))
        if prix < Decimal("0"):
            raise ValueError("Le prix d'une ligne ne peut pas être négatif")
        if quantite <= Decimal("0"):
            raise ValueError("La quantité doit être strictement positive")
    sous_total = sum(
        (Decimal(str(line["prix"])) * Decimal(str(line.get("quantite", 1))) for line in lignes),
        Decimal("0.000"),
    )
    apres_remise = sous_total * (Decimal("100") - remise_globale_pct) / Decimal("100")
    montant_tva = apres_remise * taux_tva
    total_ttc = apres_remise + montant_tva
    return {
        "sous_total": sous_total.quantize(Decimal("0.001")),
        "montant_tva": montant_tva.quantize(Decimal("0.001")),
        "total_ttc": total_ttc.quantize(Decimal("0.001")),
    }


ACTIVE_FACTURE_STATUSES = {
    StatutFacture.BROUILLON.value,
    StatutFacture.ENVOYEE.value,
    StatutFacture.PARTIELLEMENT_PAYEE.value,
    StatutFacture.PAYEE.value,
}


def _normalize_label(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _dossier_lines(dossier: DossierMedical) -> list[dict]:
    return [
        {"description": item.get("nom", ""), "prix": item.get("prix", 0), "quantite": 1}
        for item in (dossier.actes_details or [])
        if item.get("nom")
    ]


def _same_lines(dossier: DossierMedical, facture: Facture) -> bool:
    dossier_lines = _dossier_lines(dossier)
    invoice_lines = facture.actes or []
    if not dossier_lines or not invoice_lines or len(dossier_lines) != len(invoice_lines):
        return False
    expected = sorted(
        (_normalize_label(line["description"]), Decimal(str(line["prix"])), int(line.get("quantite", 1)))
        for line in dossier_lines
    )
    actual = sorted(
        (_normalize_label(line.get("description")), Decimal(str(line.get("prix", 0))), int(line.get("quantite", 1)))
        for line in invoice_lines
    )
    return expected == actual


async def find_active_facture_for_dossier(db, dossier: DossierMedical, clinic_id: int) -> Facture | None:
    """Retrouve une facture active explicitement ou historiquement liée au dossier.

    Le fallback par patient + rendez-vous/lignes permet de réparer les données
    créées avant l’introduction de dossier_id, sans fusionner des prestations
    ambiguës. Une facture annulée ne bloque jamais une nouvelle facturation.
    """
    linked = await db.execute(
        select(Facture)
        .where(
            Facture.dossier_id == dossier.id,
            Facture.clinic_id == clinic_id,
            Facture.statut.in_(ACTIVE_FACTURE_STATUSES),
        )
        .order_by(Facture.created_at.desc())
        .limit(1)
    )
    facture = linked.scalar_one_or_none()
    if facture:
        return facture

    query = select(Facture).where(
        Facture.patient_id == dossier.patient_id,
        Facture.clinic_id == clinic_id,
        Facture.statut.in_(ACTIVE_FACTURE_STATUSES),
    )
    if dossier.rdv_id is not None:
        query = query.where(
            or_(Facture.rdv_id == dossier.rdv_id, Facture.rdv_id.is_(None))
        )
    else:
        query = query.where(Facture.date_emission == dossier.date_acte.date())
    candidates = list((await db.execute(query)).scalars().all())
    matches = [candidate for candidate in candidates if _same_lines(dossier, candidate)]
    return matches[0] if len(matches) == 1 else None


def _resolve_service_clinic(clinic_id: int | None) -> int:
    if clinic_id and clinic_id > 0:
        return int(clinic_id)
    settings = get_settings()
    if settings.env in {"test", "development"}:
        return int(settings.clinic_id or 1)
    raise ValueError("Contexte clinique obligatoire")


async def create_facture(data: dict, created_by: int, db, clinic_id: int | None = None) -> Facture:
    clinic_id = _resolve_service_clinic(clinic_id)
    currency = await get_setting("clinic.currency", db, clinic_id=clinic_id) or {
        "currency_code": "TND", "currency_symbol": "DT"
    }
    currency_code = str(currency.get("currency_code", "TND")).strip().upper()[:3]
    currency_symbol = str(currency.get("currency_symbol", "DT")).strip()[:8]
    dossier = None
    if data.get("dossier_id") is not None:
        dossier_result = await db.execute(select(DossierMedical).where(
            DossierMedical.id == data["dossier_id"],
            DossierMedical.patient_id == data["patient_id"],
            DossierMedical.clinic_id == clinic_id,
        ))
        dossier = dossier_result.scalar_one_or_none()
        if not dossier:
            raise ValueError("Dossier médical non trouvé")
        existing = await find_active_facture_for_dossier(db, dossier, clinic_id)
        if existing:
            raise ValueError(
                f"Ce dossier est déjà rattaché à la facture {existing.numero_facture}"
            )

    result = await db.execute(select(Patient).where(
        Patient.id == data["patient_id"], Patient.clinic_id == clinic_id,
    ))
    patient = result.scalar_one_or_none()
    if not patient:
        raise ValueError("Patient non trouvé")

    taux_tva = Decimal(str(data.get("taux_tva", "0.190")))
    remise = Decimal(str(data.get("remise_globale_pct", "0.00")))
    actes_json = _json_lines(data.get("actes", []))
    produits_json = _json_lines(data.get("produits", []))
    totals = _compute_totals(actes_json, produits_json, remise, taux_tva)

    # _generate_numero_facture() compte les factures existantes sans
    # verrou : deux créations simultanées peuvent lire le même compte et
    # obtenir le même numéro. La contrainte unique sur numero_facture
    # (models/database.py) fait échouer l'insertion dans ce cas — on
    # regénère et on réessaie plutôt que de verrouiller une table entière
    # (portable SQLite/Postgres, contrairement à un with_for_update sur
    # un COUNT qui ne verrouille aucune ligne réelle).
    max_essais = 5
    for tentative in range(max_essais):
        facture = Facture(
            clinic_id=clinic_id,
            patient_id=data["patient_id"],
            rdv_id=data.get("rdv_id") or (dossier.rdv_id if dossier else None),
            dossier_id=dossier.id if dossier else None,
            numero_facture=await _generate_numero_facture(db),
            currency_code=currency_code,
            currency_symbol=currency_symbol,
            date_emission=data.get("date_emission", date.today()),
            date_echeance=data.get("date_echeance"),
            actes=actes_json,
            produits=produits_json,
            taux_tva=taux_tva,
            remise_globale_pct=remise,
            notes=data.get("notes"),
            created_by=created_by,
            statut=StatutFacture.BROUILLON.value,
            **totals,
        )
        db.add(facture)
        try:
            await db.flush()
            if dossier:
                dossier.statut_facturation = "facture"
            else:
                # Réconcilie les factures manuelles créées avant l’acte médical.
                reconciliation = await db.execute(select(DossierMedical).where(
                    DossierMedical.patient_id == facture.patient_id,
                    DossierMedical.clinic_id == clinic_id,
                    DossierMedical.statut_facturation == "en_attente",
                ))
                matching_dossiers = [
                    candidate for candidate in reconciliation.scalars().all()
                    if _same_lines(candidate, facture)
                    and (candidate.rdv_id is None or facture.rdv_id == candidate.rdv_id)
                ]
                if len(matching_dossiers) == 1:
                    dossier = matching_dossiers[0]
                    facture.dossier_id = dossier.id
                    dossier.statut_facturation = "facture"
            await db.flush()
            return facture
        except IntegrityError:
            await db.rollback()
            if tentative == max_essais - 1:
                raise ValueError("Impossible de générer un numéro de facture unique, réessayez")
            continue


async def marquer_payee(facture_id: int, mode_paiement: str, db, clinic_id: int | None = None) -> dict:
    clinic_id = _resolve_service_clinic(clinic_id)
    result = await db.execute(select(Facture).where(
        Facture.id == facture_id, Facture.clinic_id == clinic_id,
    ))
    facture = result.scalar_one_or_none()
    if not facture:
        raise ValueError("Facture non trouvée")
    if facture.statut == StatutFacture.PAYEE.value:
        raise ValueError("Cette facture est déjà marquée comme payée")
    if facture.statut == StatutFacture.ANNULEE.value:
        raise ValueError("Impossible de payer une facture annulée")
    if facture.statut not in {StatutFacture.BROUILLON.value, StatutFacture.ENVOYEE.value, StatutFacture.PARTIELLEMENT_PAYEE.value}:
        raise ValueError(f"Transition de paiement impossible depuis le statut {facture.statut}")
    mode = (mode_paiement or "").strip().lower()
    if mode not in {"especes", "carte", "virement", "cheque", "autre"}:
        raise ValueError("Mode de paiement invalide")

    facture.statut = StatutFacture.PAYEE.value
    facture.mode_paiement = mode_paiement
    await db.flush()

    patient_result = await db.execute(select(Patient).where(
        Patient.id == facture.patient_id, Patient.clinic_id == clinic_id,
    ))
    patient = patient_result.scalar_one_or_none()

    commission = None
    if patient and patient.commercial_id:
        commission = await create_commission(
            commercial_id=patient.commercial_id, patient_id=patient.id,
            facture_id=facture.id, montant_ca=facture.total_ttc, db=db,
            clinic_id=facture.clinic_id,
        )

    points_gagnes = int(facture.total_ttc // POINTS_PAR_UNITE)
    if points_gagnes > 0:
        await add_points(
            patient_id=facture.patient_id, points=points_gagnes,
            motif=f"Facture {facture.numero_facture}", db=db,
            reference_id=facture.id, reference_type="facture",
            clinic_id=facture.clinic_id,
        )

    return {"facture": facture, "commission": commission, "points_gagnes": points_gagnes}


async def annuler_facture(facture_id: int, motif: str, db, clinic_id: int | None = None) -> Facture:
    clinic_id = _resolve_service_clinic(clinic_id)
    result = await db.execute(select(Facture).where(
        Facture.id == facture_id, Facture.clinic_id == clinic_id,
    ))
    facture = result.scalar_one_or_none()
    if not facture:
        raise ValueError("Facture non trouvée")
    if facture.statut == StatutFacture.PAYEE.value:
        raise ValueError("Impossible d'annuler une facture déjà payée — émettre un avoir")
    if facture.statut == StatutFacture.ANNULEE.value:
        raise ValueError("Cette facture est déjà annulée")
    motif = (motif or "").strip()
    if len(motif) < 3:
        raise ValueError("Un motif d'annulation explicite est obligatoire")

    facture.statut = StatutFacture.ANNULEE.value
    facture.notes = f"{facture.notes or ''}\n[ANNULÉE] {motif}".strip()
    await db.flush()
    return facture


async def list_factures(db, clinic_id: int | None = None, patient_id: Optional[int] = None, statut: Optional[str] = None,
                         skip: int = 0, limit: int = 100) -> tuple[list[Facture], int]:
    clinic_id = _resolve_service_clinic(clinic_id)
    query = select(Facture).where(Facture.clinic_id == clinic_id)
    count_query = select(func.count(Facture.id)).where(Facture.clinic_id == clinic_id)
    if patient_id:
        query = query.where(Facture.patient_id == patient_id)
        count_query = count_query.where(Facture.patient_id == patient_id)
    if statut:
        query = query.where(Facture.statut == statut)
        count_query = count_query.where(Facture.statut == statut)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(
        query.order_by(Facture.created_at.desc()).offset(skip).limit(limit)
    )
    return list(result.scalars().all()), total
