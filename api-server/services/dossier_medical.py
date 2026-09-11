"""
AutoCommerce Clinic — Dossier médical chiffré
Chiffrement Fernet, timeline, export PDF
"""

import io
from datetime import datetime, time
from typing import List, Optional

from cryptography.fernet import Fernet
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import get_settings
from models.database import (
    DossierMedical, Patient, Utilisateur, ActeMedical, Facture, RendezVous,
    PhotoClinic, Consentement, RoleEnum, UtilisationLot, LotInjectable, SuiviPostActe,
    ProduitInjectable,
)
from services.consentement import verify_consent
from services.audit_medical import log_access
from services.branding import get_branding_context

settings = get_settings()


def _resolve_clinic(clinic_id: int | None) -> int:
    if clinic_id and clinic_id > 0:
        return int(clinic_id)
    if settings.env in {"test", "development"}:
        return int(settings.clinic_id or 1)
    if settings.is_internal_single_clinic and settings.clinic_id:
        return int(settings.clinic_id)
    raise ValueError("Contexte clinique obligatoire")


def get_fernet() -> Fernet:
    """Retourne une instance Fernet pour le chiffrement."""
    if not settings.fernet_key:
        raise ValueError("FERNET_KEY non configurée")
    return Fernet(settings.fernet_key.encode())


def encrypt_field(plaintext: str) -> str:
    """Chiffre un champ texte avec Fernet."""
    if not plaintext:
        return ""
    f = get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_field(ciphertext: str) -> str:
    """Déchiffre un champ texte avec Fernet."""
    if not ciphertext:
        return ""
    f = get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


async def create_dossier(
    patient_id: int,
    praticien_id: int,
    rdv_id: Optional[int],
    data: dict,
    db: AsyncSession,
    clinic_id: int | None = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> DossierMedical:
    """Crée un dossier médical.

    Vérifie consentement signé valide avant création.
    Chiffre les observations.
    Crée log audit.
    """
    clinic_id = _resolve_clinic(clinic_id)

    patient = await db.scalar(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == clinic_id,
            Patient.anonymized_at.is_(None),
        )
    )
    if not patient:
        raise ValueError("Patient non trouvé dans cette clinique")

    praticien = await db.scalar(
        select(Utilisateur).where(
            Utilisateur.id == praticien_id,
            Utilisateur.clinic_id == clinic_id,
            Utilisateur.is_active,
            Utilisateur.role.in_([RoleEnum.MEDECIN.value, RoleEnum.ESTHETICIENNE.value]),
        )
    )
    if not praticien:
        raise ValueError("Praticien non trouvé dans cette clinique")

    # L’acte, le rendez-vous, le patient et le praticien doivent rester dans
    # le même tenant, même si les clés étrangères sont globales.
    acte_id = data.get("acte_id")
    if acte_id is not None:
        acte = await db.scalar(
            select(ActeMedical).where(
                ActeMedical.id == acte_id,
                ActeMedical.clinic_id == clinic_id,
                ActeMedical.is_active,
            )
        )
        if not acte:
            raise ValueError("Acte non trouvé dans cette clinique")

    if rdv_id is not None:
        rdv = await db.scalar(
            select(RendezVous).where(
                RendezVous.id == rdv_id,
                RendezVous.clinic_id == clinic_id,
            )
        )
        if not rdv or rdv.patient_id != patient_id or rdv.praticien_id != praticien_id:
            raise ValueError("Rendez-vous incohérent ou hors clinique")
        if acte_id is not None and rdv.acte_id not in (None, acte_id):
            raise ValueError("L’acte du rendez-vous ne correspond pas au dossier")

    statut_clinique = str(data.get("statut_clinique") or "cloture")
    if statut_clinique not in {"brouillon", "cloture"}:
        raise ValueError("Statut clinique invalide")
    if statut_clinique == "cloture":
        if acte_id is None:
            raise ValueError("Un acte est requis pour clôturer le dossier médical")
        has_consent = await verify_consent(patient_id, acte_id, db, clinic_id=clinic_id)
        if not has_consent:
            raise ValueError("Consentement non signé ou expiré pour cet acte")

    # Chiffrer observations
    observations = data.get("observations", "")
    observations_enc = encrypt_field(observations) if observations else None

    dossier = DossierMedical(
        clinic_id=clinic_id,
        patient_id=patient_id,
        praticien_id=praticien_id,
        rdv_id=rdv_id,
        acte_id=acte_id,
        date_acte=data.get("date_acte", datetime.utcnow()),
        zones_traitees=data.get("zones_traitees"),
        produits_utilises=data.get("produits_utilises"),
        observations_enc=observations_enc,
        effets_secondaires=data.get("effets_secondaires"),
        satisfaction_patient=data.get("satisfaction_patient"),
        suivi_requis=data.get("suivi_requis", False),
        date_suivi_recommandee=data.get("date_suivi_recommandee"),
        actes_details=data.get("actes_details", []),
        statut_clinique=statut_clinique,
        statut_facturation="brouillon" if statut_clinique == "brouillon" else "en_attente",
    )
    db.add(dossier)
    await db.flush()

    if statut_clinique == "cloture":
        await _reconcile_dossier_facture(db, dossier, clinic_id)
        await _ensure_post_acte_followup(db, dossier, praticien_id, clinic_id)

    # Log audit
    await log_access(
        db=db,
        utilisateur_id=praticien_id,
        patient_id=patient_id,
        action="CREATE_DOSSIER",
        resource_type="dossier",
        resource_id=dossier.id,
        ip_address=ip_address,
        user_agent=user_agent,
        clinic_id=clinic_id,
        details={"acte_id": acte_id, "rdv_id": rdv_id},
    )

    return dossier


async def _reconcile_dossier_facture(db: AsyncSession, dossier: DossierMedical, clinic_id: int) -> None:
    """Rattache une facture existante uniquement lorsqu’un dossier est clôturé."""
    from services.factures import find_active_facture_for_dossier
    existing_facture = await find_active_facture_for_dossier(db, dossier, clinic_id)
    if existing_facture:
        dossier.statut_facturation = "facture"
        existing_facture.dossier_id = dossier.id
        await db.flush()


async def _ensure_post_acte_followup(
    db: AsyncSession, dossier: DossierMedical, praticien_id: int, clinic_id: int,
) -> None:
    """Crée au plus un suivi persistant quand le praticien a demandé un contrôle."""
    if not dossier.suivi_requis or not dossier.date_suivi_recommandee:
        return
    existing = await db.scalar(select(SuiviPostActe).where(
        SuiviPostActe.clinic_id == clinic_id,
        SuiviPostActe.dossier_id == dossier.id,
        SuiviPostActe.type_suivi == "controle_post_acte",
        SuiviPostActe.statut.in_(["a_faire", "en_cours"]),
    ))
    if existing:
        return
    db.add(SuiviPostActe(
        clinic_id=clinic_id,
        patient_id=dossier.patient_id,
        dossier_id=dossier.id,
        type_suivi="controle_post_acte",
        echeance_at=datetime.combine(dossier.date_suivi_recommandee, time.min),
        assigne_a_id=praticien_id,
        notes="Suivi post-acte créé depuis le dossier clinique clôturé.",
        created_by=praticien_id,
    ))
    await db.flush()


async def close_dossier(
    *, patient_id: int, dossier_id: int, praticien_id: int, db: AsyncSession,
    clinic_id: int | None = None, ip_address: Optional[str] = None, user_agent: Optional[str] = None,
) -> DossierMedical:
    """Clôture un brouillon de son praticien après consentement spécifique."""
    clinic_id = _resolve_clinic(clinic_id)
    dossier = await db.scalar(select(DossierMedical).where(
        DossierMedical.id == dossier_id,
        DossierMedical.patient_id == patient_id,
        DossierMedical.praticien_id == praticien_id,
        DossierMedical.clinic_id == clinic_id,
    ))
    if not dossier:
        raise ValueError("Brouillon introuvable ou non attribué au praticien connecté")
    if dossier.statut_clinique == "cloture":
        return dossier
    if dossier.acte_id is None:
        raise ValueError("Sélectionnez un acte avant de clôturer le dossier")
    if not await verify_consent(patient_id, dossier.acte_id, db, clinic_id=clinic_id):
        raise ValueError("Consentement non signé ou expiré pour cet acte")

    dossier.statut_clinique = "cloture"
    dossier.statut_facturation = "en_attente"
    await _reconcile_dossier_facture(db, dossier, clinic_id)
    await _ensure_post_acte_followup(db, dossier, praticien_id, clinic_id)
    await log_access(
        db=db, utilisateur_id=praticien_id, patient_id=patient_id,
        action="CLOSE_DOSSIER", resource_type="dossier", resource_id=dossier.id,
        ip_address=ip_address, user_agent=user_agent, clinic_id=clinic_id,
        details={"acte_id": dossier.acte_id},
    )
    await db.flush()
    return dossier


async def get_timeline_patient(
    patient_id: int,
    db: AsyncSession,
    utilisateur_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_role: Optional[str] = None,
    clinic_id: int | None = None
) -> List[dict]:
    """Timeline chronologique de tous les dossiers avec photos et produits."""
    clinic_id = _resolve_clinic(clinic_id)
    if utilisateur_id:
        await log_access(
            db=db, utilisateur_id=utilisateur_id, patient_id=patient_id,
            action="READ_TIMELINE", resource_type="dossier_timeline", resource_id=patient_id,
            ip_address=ip_address,
            clinic_id=clinic_id,
        )

    result = await db.execute(
        select(DossierMedical, ActeMedical, Utilisateur)
        .join(ActeMedical, DossierMedical.acte_id == ActeMedical.id, isouter=True)
        .join(Utilisateur, DossierMedical.praticien_id == Utilisateur.id)
        .where(DossierMedical.patient_id == patient_id)
        .where(DossierMedical.clinic_id == clinic_id)
        .order_by(DossierMedical.date_acte.desc())
    )

    timeline = []
    for dossier, acte, praticien in result.all():
        # Photos associées
        photos_result = await db.execute(
            select(PhotoClinic)
            .where(PhotoClinic.dossier_id == dossier.id)
            .where(PhotoClinic.clinic_id == clinic_id)
            .where(~PhotoClinic.is_deleted)
        )
        photos = [
            {"id": p.id, "type": p.type, "zone": p.zone_anatomique, "url": p.url_thumbnail}
            for p in photos_result.scalars().all()
        ]

        # Produits injectés (traçabilité)
        utilisations_result = await db.execute(
            select(UtilisationLot, LotInjectable, ProduitInjectable)
            .join(LotInjectable, UtilisationLot.lot_id == LotInjectable.id)
            .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
            .where(UtilisationLot.dossier_id == dossier.id)
        .where(UtilisationLot.clinic_id == clinic_id)
        )
        produits = [
            {
                "produit": p.nom,
                "lot": lot.numero_lot,
                "quantite": float(u.quantite_utilisee),
                "unite": u.unite,
            }
            for u, lot, p in utilisations_result.all()
        ]

        facture_result = await db.execute(
            select(Facture)
            .where(Facture.dossier_id == dossier.id)
            .where(Facture.clinic_id == clinic_id)
            .where(Facture.statut != "annulee")
            .order_by(Facture.date_emission.desc())
            .limit(1)
        )
        facture = facture_result.scalar_one_or_none()

        # Déchiffrer observations (SAUF pour DIRECTRICE)
        if user_role == "directrice":
            observations = "[ACCÈS MÉDICAL RÉSERVÉ]"
        else:
            observations = decrypt_field(dossier.observations_enc) if dossier.observations_enc else ""

        timeline.append({
            "dossier_id": dossier.id,
            "date": dossier.date_acte.isoformat(),
            "acte": acte.nom if acte else "Non spécifié",
            "praticien": f"{praticien.prenom} {praticien.nom}",
            "observations": observations,
            "zones_traitees": dossier.zones_traitees,
            "produits_utilises": produits,
            "effets_secondaires": dossier.effets_secondaires if user_role != "directrice" else "[ACCÈS RÉSERVÉ]",
            "satisfaction": dossier.satisfaction_patient,
            "statut_facturation": dossier.statut_facturation,
            "facture_id": facture.id if facture else None,
            "facture_numero": facture.numero_facture if facture else None,
            "facture_statut": facture.statut if facture else None,
            "statut_clinique": dossier.statut_clinique,
            "photos": photos if user_role != "directrice" else [],
        })

    return timeline


async def export_dossier_pdf(
    patient_id: int,
    db: AsyncSession,
    user_role: Optional[str] = None,
    clinic_id: int | None = None
) -> bytes:
    """Génère un PDF complet du dossier patient.

    Inclut :
    - Infos patient (déchiffrées)
    - Timeline actes
    - Produits injectés avec lots
    - Miniatures photos (si visible_patient=True)
    - Consentements signés
    """
    clinic_id = _resolve_clinic(clinic_id)
    # Récupérer patient
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id).where(Patient.clinic_id == clinic_id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise ValueError("Patient non trouvé")

    # Créer PDF
    branding = await get_branding_context(db, clinic_id=clinic_id)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    # Titre
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor(branding["primary_color"]),
        spaceAfter=20,
    )
    story.append(Paragraph(f"{branding['clinic_name']} — Dossier Médical — {patient.prenom} {patient.nom}", title_style))
    story.append(Spacer(1, 0.3*cm))

    # Infos patient
    story.append(Paragraph("<b>Informations patient</b>", styles["Heading2"]))
    
    # Masquage des données sensibles pour DIRECTRICE
    if user_role == "directrice":
        allergies = "[ACCÈS RÉSERVÉ]"
        antecedents = "[ACCÈS RÉSERVÉ]"
    else:
        allergies = decrypt_field(patient.allergies_enc) if patient.allergies_enc else "N/A"
        antecedents = decrypt_field(patient.antecedents_medicaux_enc) if patient.antecedents_medicaux_enc else "N/A"

    info_data = [
        ["Nom", f"{patient.prenom} {patient.nom}"],
        ["Date de naissance", str(patient.date_naissance) if patient.date_naissance else "N/A"],
        ["Téléphone", patient.telephone],
        ["Email", patient.email or "N/A"],
        ["Allergies", allergies],
        ["Antécédents", antecedents],
    ]
    info_table = Table(info_data, colWidths=[4*cm, 12*cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.5*cm))

    # Timeline
    story.append(Paragraph("<b>Historique des actes</b>", styles["Heading2"]))
    timeline = await get_timeline_patient(patient_id, db, user_role=user_role, clinic_id=clinic_id)

    for entry in timeline:
        story.append(Paragraph(f"<b>{entry['date'][:10]}</b> — {entry['acte']}", styles["Heading3"]))
        story.append(Paragraph(f"Praticien : {entry['praticien']}", styles["Normal"]))
        if entry['observations']:
            story.append(Paragraph(f"Observations : {entry['observations']}", styles["Normal"]))
        if entry['produits_utilises']:
            produits_text = ", ".join([
                f"{p['produit']} ({p['quantite']} {p['unite']}) — Lot {p['lot']}"
                for p in entry['produits_utilises']
            ])
            story.append(Paragraph(f"Produits : {produits_text}", styles["Normal"]))
        story.append(Spacer(1, 0.2*cm))

    # Consentements
    consent_result = await db.execute(
        select(Consentement)
        .where(Consentement.patient_id == patient_id)
        .where(Consentement.clinic_id == clinic_id)
        .where(Consentement.est_valide)
        .order_by(Consentement.signe_le.desc())
    )
    consentements = consent_result.scalars().all()

    if consentements:
        story.append(Paragraph("<b>Consentements signés</b>", styles["Heading2"]))
        for c in consentements:
            story.append(Paragraph(
                f"{c.type_consentement} — signé le {c.signe_le.strftime('%d/%m/%Y')} via {c.methode_signature}",
                styles["Normal"]
            ))

    # Footer RGPD
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(
        f"<i>{branding['clinic_name']} — Ce document est confidentiel et protégé par le secret médical. "
        "Conformément au RGPD, vous disposez d'un droit d'accès, de rectification et de suppression de vos données.</i>",
        styles["Italic"]
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
