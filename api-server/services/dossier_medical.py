"""
AutoCommerce Clinic — Dossier médical chiffré
Chiffrement Fernet, timeline, export PDF
"""

import io
from datetime import datetime
from typing import List, Optional

from cryptography.fernet import Fernet
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as ReportImage
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import get_settings
from models.database import (
    DossierMedical, Patient, Utilisateur, ActeMedical, Facture, RendezVous,
    PhotoClinic, Consentement, UtilisationLot, LotInjectable,
    ProduitInjectable,
)
from services.consentement import verify_consent
from services.audit_medical import log_access
from services.branding import get_branding_context, resolve_logo_path
from models.episode_core import EpisodePatient

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
    draft: bool = False,
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

    episode_id = data.get("episode_id")
    if episode_id is None and rdv_id is not None:
        episode_id = await db.scalar(
            select(EpisodePatient.id).where(
                EpisodePatient.rdv_origine_id == rdv_id,
                EpisodePatient.patient_id == patient_id,
                EpisodePatient.clinic_id == clinic_id,
                EpisodePatient.statut.notin_(["cloture", "annule"]),
            ).order_by(EpisodePatient.id.desc()).limit(1)
        )

    # Un brouillon d’accueil peut être préparé avant la signature du
    # consentement. La validation/clôture médicale reste conditionnée à ce
    # consentement et ne doit jamais être déduite de la simple sauvegarde.
    has_consent = await verify_consent(patient_id, acte_id, db, clinic_id=clinic_id)
    if not draft and not has_consent:
        raise ValueError("Consentement non signé ou expiré pour cet acte")

    # Chiffrer observations
    observations = data.get("observations", "")
    observations_enc = encrypt_field(observations) if observations else None

    dossier = DossierMedical(
        clinic_id=clinic_id,
        patient_id=patient_id,
        praticien_id=praticien_id,
        rdv_id=rdv_id,
        episode_id=episode_id,
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
        statut_clinique="brouillon" if draft else "cloture",
        statut_facturation="en_attente",
    )
    db.add(dossier)
    await db.flush()

    # Réconcilier une facture manuelle créée avant le dossier médical.
    # Le service ne rattache qu’une correspondance unique patient + acte,
    # et ignore les factures annulées.
    from services.factures import find_active_facture_for_dossier
    existing_facture = await find_active_facture_for_dossier(db, dossier, clinic_id)
    if existing_facture:
        dossier.statut_facturation = "facture"
        existing_facture.dossier_id = dossier.id
        await db.flush()

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

        # Les observations et effets secondaires sont des données médicales :
        # directrice et esthéticienne voient uniquement les champs esthétiques
        # utiles à leur rôle, jamais le contenu clinique sensible.
        sensitive_fields_hidden = user_role in {"directrice", "estheticienne"}
        if sensitive_fields_hidden:
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
            "effets_secondaires": (
                dossier.effets_secondaires
                if not sensitive_fields_hidden else "[ACCÈS RÉSERVÉ]"
            ),
            "satisfaction": dossier.satisfaction_patient,
            "statut_facturation": dossier.statut_facturation,
            "facture_id": facture.id if facture else None,
            "facture_numero": facture.numero_facture if facture else None,
            "facture_statut": facture.statut if facture else None,
            "photos": photos if user_role != "directrice" else [],
        })

    return timeline




# ── Imports supplémentaires pour l'export PDF enrichi ───────
from functools import partial
import json
from xml.sax.saxutils import escape as _xml_escape
from reportlab.pdfgen import canvas as _pdfcanvas

from models.database import (
    ConsultationMedicale,
    DocumentMedicalPatient,
    PatientMedicalFact,
    PrescriptionMedicale,
)

def _normalize_role(role) -> str:
    return str(role or "").replace("RoleEnum.", "").lower()


def _esc(value) -> str:
    if value is None:
        return ""
    return _xml_escape(str(value))


def _fmt_size(size: int | None) -> str:
    if not size:
        return "N/A"
    value = float(size)
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.1f} Mo"
    if value >= 1024:
        return f"{value / 1024:.1f} Ko"
    return f"{int(value)} o"


def _decrypt_optional(ciphertext: Optional[str]) -> str:
    return decrypt_field(ciphertext) if ciphertext else ""


def _fmt_prescription_details(details) -> str:
    """Sérialise les détails d'une prescription (dict ou liste) en texte lisible."""
    if not details:
        return "Aucun détail"
    lines = []
    ordered_keys = ("medicament", "dosage", "frequence", "duree")
    if isinstance(details, list):
        for item in details:
            if isinstance(item, dict):
                parts = [f"{k}: {item[k]}" for k in ordered_keys if item.get(k)]
                for k, v in item.items():
                    if k not in ordered_keys and v not in (None, ""):
                        parts.append(f"{k}: {v}")
                lines.append(" · ".join(parts) if parts else str(item))
            else:
                lines.append(str(item))
    elif isinstance(details, dict):
        for k, v in details.items():
            if v not in (None, ""):
                lines.append(f"{k}: {v}")
    else:
        lines.append(str(details))
    return " ; ".join(lines) if lines else "Aucun détail"


def _fmt_fact_donnees(donnees) -> str:
    """Sérialise le dictionnaire de données d'un fait médical en texte lisible."""
    if not donnees:
        return "—"
    if isinstance(donnees, dict):
        return " ; ".join(f"{k}: {v}" for k, v in donnees.items() if v not in (None, ""))
    if isinstance(donnees, list):
        return " ; ".join(str(x) for x in donnees)
    return str(donnees)


class _NumberedCanvas(_pdfcanvas.Canvas):
    """Canvas reportlab ajoutant un en-tête d'export et la pagination Page X / Y."""

    header_left = ""
    header_right = ""

    def __init__(self, *args, header_left: str = "", header_right: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.header_left = header_left
        self.header_right = header_right
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def _draw_header_footer(self, page_count: int):
        width, height = A4
        self.saveState()
        # En-tête professionnel
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#333333"))
        self.drawString(1.5 * cm, height - 1.25 * cm, self.header_left)
        self.setFont("Helvetica", 8)
        self.drawRightString(width - 1.5 * cm, height - 1.25 * cm, self.header_right)
        self.setStrokeColor(colors.HexColor("#BBBBBB"))
        self.line(1.5 * cm, height - 1.45 * cm, width - 1.5 * cm, height - 1.45 * cm)
        # Pied de page paginé
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.grey)
        self.drawCentredString(width / 2, 1.0 * cm, f"Page {self._pageNumber} / {page_count}")
        self.drawRightString(width - 1.5 * cm, 1.2 * cm, f"Émis le {datetime.utcnow():%d/%m/%Y %H:%M} UTC")
        self.restoreState()


async def _collect_consultations(db: AsyncSession, patient_id: int, clinic_id: int) -> list:
    rows = (await db.execute(
        select(ConsultationMedicale, Utilisateur)
        .join(Utilisateur, ConsultationMedicale.auteur_id == Utilisateur.id)
        .where(ConsultationMedicale.patient_id == patient_id)
        .where(ConsultationMedicale.clinic_id == clinic_id)
        .order_by(ConsultationMedicale.date_consultation.desc())
    )).all()
    out = []
    for item, author in rows:
        out.append({
            "date": item.date_consultation,
            "type": item.type_consultation,
            "statut": item.statut,
            "praticien": f"{author.prenom} {author.nom}",
            "motif": _decrypt_optional(item.motif_enc),
            "demande_patient": _decrypt_optional(item.demande_patient_enc),
            "objectif": _decrypt_optional(item.objectif_enc),
            "histoire": _decrypt_optional(item.histoire_enc),
            "evolution": _decrypt_optional(item.evolution_enc),
            "traitements_precedents": _decrypt_optional(item.traitements_precedents_enc),
            "contexte": _decrypt_optional(item.contexte_enc),
            "observations": _decrypt_optional(item.observations_cliniques_enc),
            "mesures": _decrypt_optional(item.mesures_enc),
            "diagnostic": _decrypt_optional(item.diagnostic_enc),
            "indication": _decrypt_optional(item.indication_enc),
            "plan": _decrypt_optional(item.plan_therapeutique_enc),
            "contre_indications": _decrypt_optional(item.contre_indications_enc),
            "facteurs_risque": _decrypt_optional(item.facteurs_risque_enc),
            "objectifs_therapeutiques": _decrypt_optional(item.objectifs_therapeutiques_enc),
            "benefices_attendus": _decrypt_optional(item.benefices_attendus_enc),
            "risques": _decrypt_optional(item.risques_enc),
            "alternatives": _decrypt_optional(item.alternatives_enc),
            "recommandation": _decrypt_optional(item.recommandation_enc),
            "acte_propose": _decrypt_optional(item.acte_propose_enc),
            "suivi": _decrypt_optional(item.suivi_enc),
        })
    return out


async def _collect_prescriptions(db: AsyncSession, patient_id: int, clinic_id: int) -> list:
    rows = (await db.execute(
        select(PrescriptionMedicale, Utilisateur)
        .join(Utilisateur, PrescriptionMedicale.prescripteur_id == Utilisateur.id)
        .where(PrescriptionMedicale.patient_id == patient_id)
        .where(PrescriptionMedicale.clinic_id == clinic_id)
        .order_by(PrescriptionMedicale.date_prescription.desc())
    )).all()
    out = []
    for item, prescriber in rows:
        try:
            details = json.loads(decrypt_field(item.details_enc))
        except Exception:
            details = {}
        out.append({
            "date": item.date_prescription,
            "prescripteur": f"{prescriber.prenom} {prescriber.nom}",
            "statut": item.statut,
            "classification": item.classification,
            "details": details,
        })
    return out


async def _collect_faits_medicaux(db: AsyncSession, patient_id: int, clinic_id: int) -> list:
    rows = (await db.execute(
        select(PatientMedicalFact, Utilisateur)
        .join(Utilisateur, PatientMedicalFact.auteur_id == Utilisateur.id)
        .where(PatientMedicalFact.patient_id == patient_id)
        .where(PatientMedicalFact.clinic_id == clinic_id)
        .where(PatientMedicalFact.actif.is_(True))
        .order_by(PatientMedicalFact.created_at.desc())
    )).all()
    out = []
    for item, author in rows:
        try:
            donnees = json.loads(decrypt_field(item.donnees_enc))
        except Exception:
            donnees = {}
        out.append({
            "date": item.created_at,
            "type": item.type_fait,
            "verification": item.verification_status,
            "source": item.source,
            "auteur": f"{author.prenom} {author.nom}",
            "donnees": donnees,
        })
    return out


async def _collect_documents(db: AsyncSession, patient_id: int, clinic_id: int) -> list:
    rows = (await db.execute(
        select(DocumentMedicalPatient)
        .where(DocumentMedicalPatient.patient_id == patient_id)
        .where(DocumentMedicalPatient.clinic_id == clinic_id)
        .where(DocumentMedicalPatient.statut == "ACTIVE")
        .order_by(DocumentMedicalPatient.created_at.desc())
    )).scalars().all()
    out = []
    for item in rows:
        out.append({
            "date": item.created_at,
            "nom": item.nom_original,
            "mime": item.mime_type,
            "taille": _fmt_size(item.taille_octets),
            "description": _decrypt_optional(item.description_enc) or None,
            "hash": item.hash_sha256,
        })
    return out

async def export_dossier_pdf(
    patient_id: int,
    db: AsyncSession,
    user: Optional[dict] = None,
    clinic_id: int | None = None,
) -> bytes:
    """Génère un PDF complet et paginé du dossier patient.

    Enrichi avec les données cliniques structurées — consultations,
    prescriptions, faits médicaux structurés, documents/analyses importés —
    en plus de la timeline d'actes, des produits injectés (traçabilité des
    lots) et des consentements signés. En-tête d'export professionnel
    (référence unique, horodatage UTC, identité de l'exportateur,
    classification) et pagination réelle « Page X / Y » sur tout le document.

    Confidentialité : les sections cliniques structurées et les champs
    sensibles du patient restent réservés au rôle médecin ; un autre rôle
    autorisé à exporter (directrice) voit une mention d'accès réservé.
    Toute donnée libre déchiffrée est échappée avant insertion dans le PDF.
    """
    from services.documents_medicaux import read_document

    clinic_id = _resolve_clinic(
        clinic_id or (int(user["clinic_id"]) if user and user.get("clinic_id") else None)
    )
    role = _normalize_role(user.get("role") if user else None)
    is_medecin = role == "medecin"

    result = await db.execute(
        select(Patient).where(Patient.id == patient_id).where(Patient.clinic_id == clinic_id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise ValueError("Patient non trouvé")

    branding = await get_branding_context(db, clinic_id=clinic_id)
    now = datetime.utcnow()
    export_reference = f"DOS-{clinic_id:04d}-{patient_id:04d}-{now:%Y%m%d-%H%M%S}"

    exporter_name = "—"
    exporter_email = "—"
    if user:
        name_parts = [user.get("prenom"), user.get("nom")]
        exporter_name = " ".join(p for p in name_parts if p) or str(user.get("id", "—"))
        exporter_email = user.get("email") or "—"

    # ── Collecte des sections cliniques (médecin uniquement) ──
    consultations: list = []
    prescriptions: list = []
    faits: list = []
    documents: list = []
    if is_medecin:
        consultations = await _collect_consultations(db, patient_id, clinic_id)
        prescriptions = await _collect_prescriptions(db, patient_id, clinic_id)
        faits = await _collect_faits_medicaux(db, patient_id, clinic_id)
        documents = await _collect_documents(db, patient_id, clinic_id)

    timeline = await get_timeline_patient(patient_id, db, user_role=role, clinic_id=clinic_id)

    consent_result = await db.execute(
        select(Consentement)
        .where(Consentement.patient_id == patient_id)
        .where(Consentement.clinic_id == clinic_id)
        .where(Consentement.est_valide)
        .order_by(Consentement.signe_le.desc())
    )
    consentements = consent_result.scalars().all()

    # ── Champs sensibles : masquage historique pour directrice ──
    if role == "directrice":
        allergies = antecedents = contre_indications = "[ACCÈS RÉSERVÉ]"
    else:
        allergies = _decrypt_optional(patient.allergies_enc) or "N/A"
        antecedents = _decrypt_optional(patient.antecedents_medicaux_enc) or "N/A"
        contre_indications = _decrypt_optional(patient.contre_indications_enc) or "N/A"

    # ── Construction du document ──────────────────────────────
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=2.6 * cm, bottomMargin=2.2 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        title=f"Dossier médical — {patient.prenom} {patient.nom}",
        author=branding["clinic_name"],
        subject=f"Réf {export_reference} — {now:%Y-%m-%d %H:%M} UTC",
    )
    styles = getSampleStyleSheet()
    story = []

    # En-tête de marque : le logo est propre à la clinique et reste exclu
    # s’il ne provient pas du stockage branding validé.
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=17,
        textColor=colors.HexColor(branding["primary_color"]),
        spaceAfter=8,
    )
    logo_path = resolve_logo_path(branding.get("logo_url"))
    logo_cell = ""
    if logo_path:
        try:
            logo_cell = ReportImage(str(logo_path), width=2.0 * cm, height=2.0 * cm, kind="proportional")
        except Exception:
            logo_cell = ""
    title_block = Table([[
        logo_cell,
        Paragraph(_esc(f"{branding['clinic_name']} — Dossier Médical — {patient.prenom} {patient.nom}"), title_style),
    ]], colWidths=[2.5 * cm, 13.5 * cm])
    title_block.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(title_block)

    # Bloc en-tête d'export
    header_style = ParagraphStyle(
        "ExportHeader",
        parent=styles["Normal"],
        fontSize=8.5,
        textColor=colors.HexColor("#555555"),
        spaceAfter=2,
    )
    for line in (
        f"<b>Référence d'export :</b> {_esc(export_reference)}",
        f"<b>Émis le :</b> {now:%d/%m/%Y} à {now:%H:%M} (UTC)",
        f"<b>Exporté par :</b> {_esc(exporter_name)} ({_esc(exporter_email)}) — rôle {_esc(role) or 'non précisé'}",
        "<b>Classification :</b> MEDICAL_SENSITIVE — confidentiel, protégé par le secret médical et le RGPD",
    ):
        story.append(Paragraph(line, header_style))
    story.append(Spacer(1, 0.4 * cm))

    # Informations patient
    story.append(Paragraph("<b>Informations patient</b>", styles["Heading2"]))
    info_data = [
        ["Nom", _esc(f"{patient.prenom} {patient.nom}")],
        ["Date de naissance", _esc(str(patient.date_naissance) if patient.date_naissance else "N/A")],
        ["Genre", _esc(patient.genre or "N/A")],
        ["Groupe sanguin", _esc(patient.groupe_sanguin or "N/A")],
        ["Téléphone", _esc(patient.telephone or "N/A")],
        ["Email", _esc(patient.email or "N/A")],
        ["Adresse", _esc(" / ".join(x for x in [patient.adresse, patient.ville] if x) or "N/A")],
        ["Allergies", _esc(allergies)],
        ["Antécédents", _esc(antecedents)],
        ["Contre-indications", _esc(contre_indications)],
    ]
    info_table = Table(info_data, colWidths=[4 * cm, 12 * cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.5 * cm))

    # Timeline des actes
    story.append(Paragraph("<b>Historique des actes</b>", styles["Heading2"]))
    if not timeline:
        story.append(Paragraph("Aucun acte enregistré.", styles["Normal"]))
    for entry in timeline:
        story.append(Paragraph(f"<b>{_esc(entry['date'][:10])}</b> — {_esc(entry['acte'])}", styles["Heading3"]))
        story.append(Paragraph(f"Praticien : {_esc(entry['praticien'])}", styles["Normal"]))
        if entry["observations"]:
            story.append(Paragraph(f"Observations : {_esc(entry['observations'])}", styles["Normal"]))
        if entry["produits_utilises"]:
            produits_text = ", ".join(
                f"{_esc(p['produit'])} ({p['quantite']} {_esc(p['unite'])}) — Lot {_esc(p['lot'])}"
                for p in entry["produits_utilises"]
            )
            story.append(Paragraph(f"Produits : {_esc(produits_text)}", styles["Normal"]))
        story.append(Spacer(1, 0.2 * cm))

    # ── Sections cliniques structurées ───────────────────────
    if not is_medecin:
        reserved = ParagraphStyle(
            "Reserved",
            parent=styles["Normal"],
            textColor=colors.HexColor("#888888"),
            fontSize=9,
        )
        story.append(Paragraph("<b>Consultations, prescriptions, faits médicaux et documents</b>", styles["Heading2"]))
        story.append(Paragraph("[ACCÈS MÉDICAL RÉSERVÉ] — ces sections sont consultables par un médecin uniquement.", reserved))
        story.append(Spacer(1, 0.3 * cm))
    else:
        # Consultations
        story.append(Paragraph("<b>Consultations</b>", styles["Heading2"]))
        if not consultations:
            story.append(Paragraph("Aucune consultation structurée.", styles["Normal"]))
        for c in consultations:
            story.append(Paragraph(
                f"<b>{_esc(c['date'].strftime('%d/%m/%Y'))}</b> — {_esc(c['type'])} ({_esc(c['statut'])}) — Dr {_esc(c['praticien'])}",
                styles["Heading3"],
            ))
            labels = {
                "motif": "Motif", "demande_patient": "Demande du patient", "objectif": "Objectif",
                "histoire": "Histoire médicale", "evolution": "Évolution", "traitements_precedents": "Traitements précédents",
                "contexte": "Contexte", "observations": "Observations cliniques", "mesures": "Mesures et résultats",
                "diagnostic": "Diagnostic / analyse professionnelle", "indication": "Indication",
                "plan": "Plan thérapeutique", "contre_indications": "Contre-indications", "facteurs_risque": "Facteurs de risque",
                "objectifs_therapeutiques": "Objectifs thérapeutiques", "benefices_attendus": "Bénéfices attendus",
                "risques": "Risques expliqués", "alternatives": "Alternatives", "recommandation": "Recommandation",
                "acte_propose": "Acte proposé", "suivi": "Suivi recommandé",
            }
            for key, label in labels.items():
                if c.get(key):
                    story.append(Paragraph(f"{label} : {_esc(c[key])}", styles["Normal"]))
            story.append(Spacer(1, 0.2 * cm))

        # Prescriptions
        story.append(Paragraph("<b>Prescriptions</b>", styles["Heading2"]))
        if not prescriptions:
            story.append(Paragraph("Aucune prescription.", styles["Normal"]))
        for p in prescriptions:
            story.append(Paragraph(
                f"<b>{_esc(p['date'].strftime('%d/%m/%Y'))}</b> — Prescripteur : {_esc(p['prescripteur'])} — statut {_esc(p['statut'])}",
                styles["Heading3"],
            ))
            story.append(Paragraph(f"Détails : {_esc(_fmt_prescription_details(p['details']))}", styles["Normal"]))
            story.append(Spacer(1, 0.2 * cm))

        # Faits médicaux
        story.append(Paragraph("<b>Faits médicaux structurés</b>", styles["Heading2"]))
        if not faits:
            story.append(Paragraph("Aucun fait médical structuré.", styles["Normal"]))
        for f in faits:
            story.append(Paragraph(
                f"<b>{_esc(f['date'].strftime('%d/%m/%Y'))}</b> — {_esc(f['type'])} — vérification : {_esc(f['verification'])} — source : {_esc(f['source'])} — par {_esc(f['auteur'])}",
                styles["Heading3"],
            ))
            story.append(Paragraph(f"Données : {_esc(_fmt_fact_donnees(f['donnees']))}", styles["Normal"]))
            story.append(Spacer(1, 0.2 * cm))

        # Documents / analyses importés. Les photos cliniques ne sont jamais
        # incorporées à cet export : elles restent dans l'espace sécurisé.
        story.append(Paragraph("<b>Analyses, radios et documents médicaux</b>", styles["Heading2"]))
        story.append(Paragraph("Les photographies cliniques sont conservées séparément dans l'espace médical sécurisé et ne sont pas incluses dans cet export, conformément au RGPD.", styles["Normal"]))
        if not documents:
            story.append(Paragraph("Aucun document importé.", styles["Normal"]))
        for d in documents:
            story.append(Paragraph(
                f"<b>{_esc(d['nom'])}</b> — {_esc(d['mime'])} — {_esc(d['taille'])} — importé le {_esc(d['date'].strftime('%d/%m/%Y'))}",
                styles["Heading3"],
            ))
            if d["description"]:
                story.append(Paragraph(f"Description : {_esc(d['description'])}", styles["Normal"]))
            story.append(Paragraph(f"Empreinte d'intégrité (SHA-256) : {_esc(d['hash'])}", styles["Normal"]))
            # Les documents importés (radios, comptes rendus, résultats) font
            # partie du dossier. Les photos cliniques sont exclues par design.
            try:
                doc_row = next((row for row in (await db.execute(
                    select(DocumentMedicalPatient).where(
                        DocumentMedicalPatient.patient_id == patient_id,
                        DocumentMedicalPatient.clinic_id == clinic_id,
                        DocumentMedicalPatient.nom_original == d["nom"],
                        DocumentMedicalPatient.hash_sha256 == d["hash"],
                        DocumentMedicalPatient.statut == "ACTIVE",
                    )
                )).scalars().all()), None)
                if doc_row:
                    raw_doc, _ = await read_document(db, patient_id, doc_row.id, user or {}, {"ip_address": None})
                    mime = d["mime"].lower()
                    if mime.startswith("text/"):
                        text = raw_doc.decode("utf-8", errors="replace")[:12000]
                        story.append(Paragraph(f"Contenu : {_esc(text).replace(chr(10), '<br/>')}", styles["Normal"]))
                    elif mime.startswith("image/"):
                        image = ReportImage(ImageReader(io.BytesIO(raw_doc)), width=15 * cm, height=10 * cm, kind="proportional")
                        story.append(Paragraph("Aperçu du document médical :", styles["Normal"]))
                        story.append(image)
                    elif mime == "application/pdf":
                        story.append(Paragraph("Document PDF médical joint et conservé dans le dossier sécurisé. Son empreinte ci-dessus permet d'en vérifier l'intégrité.", styles["Normal"]))
            except Exception:
                story.append(Paragraph("Contenu original conservé dans le dossier sécurisé ; aperçu indisponible dans cet export.", styles["Normal"]))
            story.append(Spacer(1, 0.2 * cm))

    # Consentements signés
    if consentements:
        story.append(Paragraph("<b>Consentements signés</b>", styles["Heading2"]))
        for c in consentements:
            story.append(Paragraph(
                f"{_esc(c.type_consentement)} — signé le {c.signe_le.strftime('%d/%m/%Y')} via {_esc(c.methode_signature)}",
                styles["Normal"],
            ))

    # Footer RGPD
    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph(
        f"<i>{_esc(branding['clinic_name'])} — Ce document est confidentiel et protégé par le secret médical. "
        "Conformément au RGPD, vous disposez d'un droit d'accès, de rectification et de suppression de vos données.</i>",
        styles["Italic"],
    ))

    header_title = f"{branding['clinic_name']} — Dossier médical — {patient.prenom} {patient.nom}"
    doc.build(story, canvasmaker=partial(
        _NumberedCanvas,
        header_left=header_title,
        header_right=f"Réf {export_reference}",
    ))
    buf.seek(0)
    return buf.getvalue()
