"""
AutoCommerce Clinic — Gestion des consentements
Signature tactile, PDF archivé, validité 12 mois
"""

import base64
import io
import textwrap
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

ALLOWED_CONSENT_TYPES = {"general", "acte_medical", "simulation_ia"}

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from models.database import Consentement, Patient, ActeMedical, Utilisateur
from config import get_settings
from services.clinic_settings import _resolve_clinic_id, get_setting
from services.branding import get_branding_context

settings = get_settings()


async def _load_contract_context(
    patient_id: int,
    acte_ids: list[int],
    praticien_id: int,
    clinic_id: int,
    db: AsyncSession,
) -> tuple[Patient, Utilisateur, list[ActeMedical], dict]:
    normalized_ids = list(dict.fromkeys(acte_ids))
    if not normalized_ids or len(normalized_ids) > 10:
        raise ValueError("Sélectionnez entre un et dix actes pour le contrat de consentement.")

    patient = await db.scalar(select(Patient).where(
        Patient.id == patient_id,
        Patient.clinic_id == clinic_id,
    ))
    if not patient:
        raise ValueError("Patient non trouvé")

    praticien = await db.scalar(select(Utilisateur).where(
        Utilisateur.id == praticien_id,
        Utilisateur.clinic_id == clinic_id,
        Utilisateur.is_active,
    ))
    if not praticien:
        raise ValueError("Praticien signataire non trouvé dans votre clinique.")

    result = await db.execute(select(ActeMedical).where(
        ActeMedical.id.in_(normalized_ids),
        ActeMedical.clinic_id == clinic_id,
        ActeMedical.is_active,
    ))
    actes_by_id = {acte.id: acte for acte in result.scalars().all()}
    if len(actes_by_id) != len(normalized_ids):
        raise ValueError("Un ou plusieurs actes sélectionnés ne sont plus disponibles.")

    currency = await get_setting("clinic.currency", db, clinic_id=clinic_id)
    if not isinstance(currency, dict):
        currency = {"currency_code": "TND", "currency_symbol": "DT"}
    return patient, praticien, [actes_by_id[acte_id] for acte_id in normalized_ids], currency


def _generate_contract_content(
    patient: Patient,
    praticien: Utilisateur,
    actes: list[ActeMedical],
    currency: dict,
    clinic_name: str,
) -> tuple[str, dict]:
    symbol = str(currency.get("currency_symbol") or currency.get("currency_code") or "TND")
    patient_address = ", ".join(part for part in [patient.adresse, patient.ville] if part) or "Non renseignée"
    patient_contact = " · ".join(part for part in [patient.telephone, patient.email] if part) or "Non renseigné"
    praticien_contact = " · ".join(part for part in [praticien.telephone, praticien.email] if part) or "Non renseigné"
    lines, actes_snapshot = [], []
    total = 0.0
    for index, acte in enumerate(actes, start=1):
        price = float(acte.prix_base or 0)
        total += price
        lines.append(f"{index}. {acte.nom} — {price:,.3f} {symbol}")
        actes_snapshot.append({"id": acte.id, "nom": acte.nom, "prix": price, "devise": symbol})

    now = datetime.utcnow()
    snapshot = {
        "version": "contrat_consentement_v1",
        "genere_le": now.isoformat(),
        "clinic_name": clinic_name,
        "patient": {
            "id": patient.id,
            "nom_complet": f"{patient.prenom} {patient.nom}",
            "telephone": patient.telephone,
            "email": patient.email,
            "adresse": patient_address,
        },
        "praticien": {
            "id": praticien.id,
            "nom_complet": f"{praticien.prenom} {praticien.nom}",
            "role": str(praticien.role),
            "telephone": praticien.telephone,
            "email": praticien.email,
        },
        "actes": actes_snapshot,
        "total": total,
        "devise": symbol,
    }
    content = f"""CONTRAT DE CONSENTEMENT ÉCLAIRÉ ET D'ACCEPTATION DES SOINS

Entre la clinique {clinic_name}, représentée pour cet acte par {praticien.prenom} {praticien.nom} ({praticien.role}), ci-après « le praticien »,
coordonnées : {praticien_contact},

Et {patient.prenom} {patient.nom}, ci-après « le patient »,
coordonnées : {patient_contact}, adresse : {patient_address}.

1. OBJET DU DOCUMENT
Le présent document formalise le contrat de soins entre le patient et la clinique, l'accord tarifaire de référence et le consentement médical éclairé du patient. Ces trois éléments sont distincts : aucun ne constitue une promesse de résultat.

2. ACTES ET ACCORD TARIFAIRE AU JOUR DE LA SIGNATURE
{chr(10).join(lines)}
Total de référence : {total:,.3f} {symbol}.
Toute modification d'acte ou de tarif nécessite une information préalable du patient et, le cas échéant, un nouveau document.

3. CONSENTEMENT MÉDICAL
Le patient confirme avoir reçu une information adaptée sur la nature des actes, leurs bénéfices attendus, risques, suites possibles, alternatives et contre-indications. Il déclare avoir pu poser ses questions, avoir reçu des réponses compréhensibles et consent librement aux actes listés.

4. CONTRAT DE SOINS ET ENGAGEMENTS DES PARTIES
Le patient s'engage à communiquer les informations utiles à sa prise en charge et à respecter les recommandations de suivi. Le praticien atteste avoir délivré l'information clinique utile, vérifié l'absence de contre-indication connue au vu du dossier et assuré la traçabilité du consentement.

5. SIGNATURES
Signature du patient : recueillie électroniquement ci-dessous.
Signature et validation du praticien : {praticien.prenom} {praticien.nom}, recueillies électroniquement ci-dessous.

Date de signature : {now.strftime('%d/%m/%Y à %H:%M')}.
"""
    return content, snapshot


async def preview_contract_consent(
    patient_id: int,
    acte_ids: list[int],
    praticien_id: int,
    db: AsyncSession,
    clinic_id: Optional[int] = None,
) -> dict:
    """Prévisualise le contrat exact qui sera figé lors de la signature."""
    clinic_id = _resolve_clinic_id(clinic_id)
    patient, praticien, actes, currency = await _load_contract_context(
        patient_id, acte_ids, praticien_id, clinic_id, db
    )
    branding = await get_branding_context(db, clinic_id=clinic_id)
    content, snapshot = _generate_contract_content(
        patient, praticien, actes, currency, branding["clinic_name"]
    )
    return {"contenu": content, "snapshot": snapshot}


async def preview_contract_pdf(
    patient_id: int,
    acte_ids: list[int],
    praticien_id: int,
    db: AsyncSession,
    clinic_id: Optional[int] = None,
) -> bytes:
    """Produit un PDF de contrôle sans signature ni archivage.

    Cette version est explicitement marquée comme projet et utilise le même
    en-tête de marque que le document figé lors de la signature.
    """
    clinic_id = _resolve_clinic_id(clinic_id)
    patient, praticien, actes, currency = await _load_contract_context(
        patient_id, acte_ids, praticien_id, clinic_id, db
    )
    branding = await get_branding_context(db, clinic_id=clinic_id)
    content, _ = _generate_contract_content(
        patient, praticien, actes, currency, branding["clinic_name"]
    )
    return _render_consent_pdf(
        content=content,
        clinic_name=branding["clinic_name"],
        logo_url=branding.get("logo_url"),
        patient_signature=None,
        practitioner_signature=None,
        practitioner_name=f"{praticien.prenom} {praticien.nom}",
        signed_at=None,
        document_id=None,
        preview=True,
    )


async def verify_consent(
    patient_id: int,
    acte_id: Optional[int],
    db: AsyncSession,
    type_consentement: Optional[str] = None,
    clinic_id: Optional[int] = None,
) -> bool | Consentement:
    """Vérifie si un consentement valide existe pour ce patient et cet acte/type.

    Contrat historique conservé pour les tests/services existants :
    - sans ``type_consentement`` explicite, retourne un booléen ;
    - avec ``type_consentement`` explicite, retourne l'objet Consentement
      correspondant (ou ``False`` si absent) pour les services qui ont besoin
      de son ``id``.
    """
    clinic_id = _resolve_clinic_id(clinic_id)
    limit_date = datetime.utcnow() - timedelta(days=365)  # 12 mois

    query = select(Consentement).where(
        and_(
            Consentement.patient_id == patient_id,
            Consentement.clinic_id == clinic_id,
            Consentement.est_valide,
            Consentement.signe_le >= limit_date,
        )
    )

    if type_consentement:
        query = query.where(Consentement.type_consentement == type_consentement)
    elif acte_id is not None:
        query = query.where(Consentement.acte_id == acte_id)
    else:
        query = query.where(Consentement.type_consentement == "general")

    result = await db.execute(query.limit(1))
    consentement = result.scalar_one_or_none()

    if type_consentement:
        return consentement or False
    return consentement is not None


async def sign_consent(
    patient_id: int,
    acte_id: Optional[int],
    signature_b64: str,
    method: str,
    ip_address: Optional[str],
    db: AsyncSession,
    type_consentement: Optional[str] = None,
    clinic_id: Optional[int] = None,
    acte_ids: Optional[list[int]] = None,
    praticien_id: Optional[int] = None,
    attestation_praticien: bool = False,
    signature_praticien_b64: Optional[str] = None,
) -> Consentement:
    """Signe un consentement.

    Sauvegarde signature base64.
    Génère PDF consentement signé.
    Marque est_valide=True.
    """
    clinic_id = _resolve_clinic_id(clinic_id)

    consent_type = type_consentement or ("acte_medical" if acte_id else "general")
    if consent_type not in ALLOWED_CONSENT_TYPES:
        raise ValueError("Type de consentement invalide")
    contract_snapshot = None
    praticien_signataire_id = None
    acte = None
    if consent_type == "acte_medical":
        selected_acte_ids = list(dict.fromkeys(acte_ids or ([acte_id] if acte_id else [])))
        if not selected_acte_ids:
            raise ValueError("Un consentement acte_medical requiert au moins un acte_id")
        if praticien_id:
            if not attestation_praticien or not signature_praticien_b64:
                raise ValueError("L'attestation et la signature du praticien sont requises pour signer le contrat de consentement.")
            patient, praticien, actes, currency = await _load_contract_context(
                patient_id, selected_acte_ids, praticien_id, clinic_id, db
            )
            acte = actes[0]
            acte_id = acte.id
            branding = await get_branding_context(db, clinic_id=clinic_id)
            contenu, contract_snapshot = _generate_contract_content(
                patient, praticien, actes, currency, branding["clinic_name"]
            )
            praticien_signataire_id = praticien.id
        else:
            # Compatibilité des intégrations historiques de service. Le parcours
            # HTTP clinique fournit toujours un praticien et produit un contrat.
            patient = await db.scalar(select(Patient).where(
                Patient.id == patient_id, Patient.clinic_id == clinic_id
            ))
            acte = await db.scalar(select(ActeMedical).where(
                ActeMedical.id == selected_acte_ids[0], ActeMedical.clinic_id == clinic_id
            ))
            if not patient or not acte:
                raise ValueError("Patient ou acte médical non trouvé")
            acte_id = acte.id
            contenu = _generate_consent_content(patient, acte, consent_type)
    else:
        patient = await db.scalar(select(Patient).where(
            Patient.id == patient_id, Patient.clinic_id == clinic_id
        ))
        if not patient:
            raise ValueError("Patient non trouvé")
        if acte_id:
            acte = await db.scalar(select(ActeMedical).where(
                ActeMedical.id == acte_id, ActeMedical.clinic_id == clinic_id
            ))
            if not acte:
                raise ValueError("Acte médical non trouvé")
        contenu = _generate_consent_content(patient, acte, consent_type)

    consentement = Consentement(
        clinic_id=clinic_id,
        patient_id=patient_id,
        acte_id=acte_id,
        type_consentement=consent_type,
        contenu_signe=contenu,
        contrat_snapshot=contract_snapshot,
        praticien_signataire_id=praticien_signataire_id,
        attestation_praticien=attestation_praticien if consent_type == "acte_medical" else False,
        signature_praticien_base64=signature_praticien_b64 if consent_type == "acte_medical" else None,
        signe_le=datetime.utcnow(),
        methode_signature=method,
        signature_base64=signature_b64,
        ip_address=ip_address,
        est_valide=True,
    )
    db.add(consentement)
    await db.flush()

    # Générer PDF
    branding = await get_branding_context(db, clinic_id=clinic_id)
    pdf_bytes = _generate_consent_pdf(
        consentement,
        patient,
        acte,
        branding["clinic_name"],
        branding.get("logo_url"),
    )

    # Sauvegarder PDF
    import os
    pdf_path = f"{settings.data_dir}/uploads/consentement_{consentement.id}.pdf"
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    # Mettre à jour patient
    if not patient.consentement_rgpd_signe_le:
        patient.consentement_rgpd_signe_le = datetime.utcnow()

    return consentement


def _generate_consent_content(
    patient: Patient,
    acte: Optional[ActeMedical],
    consent_type: str,
) -> str:
    """Génère le texte du consentement."""
    if consent_type == "simulation_ia":
        return f"""CONSENTEMENT SPÉCIFIQUE — SIMULATION IA

Je soussigné(e) {patient.prenom} {patient.nom}, né(e) le {patient.date_naissance or 'N/A'},
accepte la génération d'une simulation visuelle par intelligence artificielle à partir
de mes photographies médicales.

Je reconnais que cette simulation est non contractuelle, purement illustrative et ne
constitue ni une promesse de résultat ni un acte médical.

J'ai été informé(e) des finalités de traitement, des limites techniques du rendu et de
mes droits relatifs à mes données de santé et à mes images.

Date : {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}
"""

    acte_nom = acte.nom if acte else "les actes médicaux esthétiques"

    return f"""CONSENTEMENT ÉCLAIRÉ

Je soussigné(e) {patient.prenom} {patient.nom}, né(e) le {patient.date_naissance or 'N/A'},
déclare avoir été informé(e) par le praticien des risques, bénéfices et alternatives
concernant {acte_nom}.

J'ai eu l'occasion de poser toutes les questions nécessaires et j'ai reçu des réponses
satisfaisantes.

Je consens librement et en pleine connaissance de cause à recevoir {acte_nom}.

Date : {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}
"""


def _generate_consent_pdf(
    consentement: Consentement,
    patient: Patient,
    acte: Optional[ActeMedical],
    clinic_name: str,
    logo_url: Optional[str] = None,
) -> bytes:
    """Génère le PDF du consentement signé."""
    practitioner_name = None
    if consentement.contrat_snapshot:
        practitioner_name = (consentement.contrat_snapshot.get("praticien") or {}).get("nom_complet")
    return _render_consent_pdf(
        content=consentement.contenu_signe or "",
        clinic_name=clinic_name,
        logo_url=logo_url,
        patient_signature=consentement.signature_base64,
        practitioner_signature=consentement.signature_praticien_base64 if consentement.contrat_snapshot else None,
        practitioner_name=practitioner_name,
        signed_at=consentement.signe_le,
        document_id=consentement.id,
        preview=False,
    )


def _branding_logo_path(logo_url: Optional[str]) -> Optional[str]:
    """Résout uniquement un logo géré localement dans le répertoire branding."""
    if not logo_url or not logo_url.startswith("/static/branding/"):
        return None
    try:
        relative = Path(logo_url.removeprefix("/static/branding/"))
        base = settings.branding_dir.resolve()
        candidate = (base / relative).resolve()
        if base not in candidate.parents or not candidate.is_file():
            return None
        return str(candidate)
    except (OSError, ValueError):
        return None


def _draw_signature(
    c: canvas.Canvas,
    signature_b64: Optional[str],
    x: float,
    y: float,
    placeholder_offset_cm: float = 0.55,
) -> None:
    if not signature_b64:
        c.setFont("Helvetica", 9)
        c.drawString(x, y - placeholder_offset_cm * cm, "[À recueillir avant signature]")
        return
    try:
        sig_data = base64.b64decode(signature_b64.split(",")[-1])
        c.drawImage(
            ImageReader(io.BytesIO(sig_data)), x, y - 3.2 * cm,
            width=7 * cm, height=2.5 * cm, preserveAspectRatio=True,
        )
    except Exception:
        c.setFont("Helvetica", 9)
        c.drawString(x, y - 0.55 * cm, "[Signature numérique enregistrée]")


def _render_consent_pdf(
    *,
    content: str,
    clinic_name: str,
    logo_url: Optional[str],
    patient_signature: Optional[str],
    practitioner_signature: Optional[str],
    practitioner_name: Optional[str],
    signed_at: Optional[datetime],
    document_id: Optional[int],
    preview: bool,
) -> bytes:
    """Rend l’aperçu et le PDF archivé à partir d’une même mise en page."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    title = "PROJET — CONTRAT DE CONSENTEMENT" if preview else "CONTRAT DE CONSENTEMENT ÉCLAIRÉ"
    logo_path = _branding_logo_path(logo_url)

    def draw_header() -> float:
        text_x = 2 * cm
        if logo_path:
            try:
                c.drawImage(ImageReader(logo_path), 2 * cm, 26.15 * cm, width=1.35 * cm, height=1.35 * cm, preserveAspectRatio=True)
                text_x = 3.65 * cm
            except Exception:
                text_x = 2 * cm
        c.setFont("Helvetica-Bold", 15)
        c.drawString(text_x, 27 * cm, title)
        c.line(2 * cm, 26.5 * cm, 19 * cm, 26.5 * cm)
        c.setFont("Helvetica", 8)
        c.drawRightString(19 * cm, 27 * cm, clinic_name)
        if preview:
            c.setFillColorRGB(0.62, 0.45, 0.04)
            c.drawRightString(19 * cm, 25.95 * cm, "Aperçu non signé — à relire avant signature")
            c.setFillColorRGB(0, 0, 0)
        return 25.7 * cm

    y = draw_header()
    c.setFont("Helvetica", 10)
    for source_line in content.split("\n"):
        wrapped_lines = textwrap.wrap(source_line, width=105) or [""]
        for line in wrapped_lines:
            if y < 3 * cm:
                c.showPage()
                y = draw_header()
                c.setFont("Helvetica", 10)
            c.drawString(2 * cm, y, line)
            y -= 0.48 * cm

    if y < 6 * cm:
        c.showPage()
        y = draw_header()
    y -= 0.25 * cm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, y, "Signature électronique du patient :")
    _draw_signature(c, patient_signature, 2 * cm, y)

    c.setFont("Helvetica-Bold", 10)
    c.drawString(10.5 * cm, y, "Signature électronique du praticien :")
    c.setFont("Helvetica", 9)
    c.drawString(10.5 * cm, y - 0.55 * cm, practitioner_name or "Praticien non renseigné")
    _draw_signature(c, practitioner_signature, 10.5 * cm, y, placeholder_offset_cm=1.1)

    c.setFont("Helvetica", 8)
    generated_at = signed_at or datetime.utcnow()
    label = "Aperçu généré" if preview else "Document signé généré"
    identifier = f" — ID: {document_id}" if document_id else ""
    c.drawString(2 * cm, 1.5 * cm, f"{label} le {generated_at.strftime('%d/%m/%Y %H:%M')}{identifier}")
    c.drawString(2 * cm, 1 * cm, f"{clinic_name} — Document confidentiel{', non signé' if preview else ''}")

    c.save()
    buf.seek(0)
    return buf.getvalue()
