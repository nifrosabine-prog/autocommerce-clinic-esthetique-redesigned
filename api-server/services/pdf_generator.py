"""
AutoCommerce Clinic — Générateur PDF (Factures et Devis)
Documents professionnels, personnalisés par clinique et adaptés à l'impression.
"""
import io
from decimal import Decimal
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as ReportImage
from models.database import Facture, Patient
from services.branding import resolve_logo_path


def _safe_color(value: str | None, fallback: str) -> colors.Color:
    try:
        return colors.HexColor(value or fallback)
    except ValueError:
        return colors.HexColor(fallback)


async def generate_invoice_pdf(facture: Facture, patient: Patient, clinic: dict) -> bytes:
    """Génère une facture ou un devis PDF personnalisé par clinique."""
    buffer = io.BytesIO()
    primary = _safe_color(clinic.get("primary_color"), "#0F4C81")
    secondary = _safe_color(clinic.get("secondary_color"), "#0F172A")
    currency_symbol = facture.currency_symbol or clinic.get("currency", {}).get("currency_symbol", "DT")
    title = "FACTURE" if facture.statut != "brouillon" else "DEVIS"
    clinic_name = clinic.get("clinic_name", "AutoCommerce Clinic")
    logo_path = resolve_logo_path(clinic.get("logo_url"))

    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(primary)
        canvas.setLineWidth(0.6)
        canvas.line(1.5 * cm, 1.35 * cm, A4[0] - 1.5 * cm, 1.35 * cm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(1.5 * cm, 0.9 * cm, f"{clinic_name} — Document généré par AutoCommerce Clinic")
        canvas.drawRightString(A4[0] - 1.5 * cm, 0.9 * cm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm,
        topMargin=1.7 * cm, bottomMargin=1.9 * cm,
        title=f"{title} — {facture.numero_facture}", author=clinic_name,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Meta", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=colors.HexColor("#475569")))
    styles.add(ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#475569")))
    elements = []

    logo_cell = ""
    if logo_path:
        try:
            logo_cell = ReportImage(str(logo_path), width=2.0 * cm, height=2.0 * cm, kind="proportional")
        except Exception:
            logo_cell = ""
    brand_text = Paragraph(f"<font color='#FFFFFF'><b>{clinic_name}</b><br/><font size='9'>{clinic.get('address', '')} {clinic.get('phone', '')}</font></font>", styles["Normal"])
    title_text = Paragraph(f"<font color='#FFFFFF'><b>{title}</b><br/><font size='9'>{facture.numero_facture}</font></font>", styles["Normal"])
    header = Table([[logo_cell, brand_text, title_text]], colWidths=[2.5 * cm, 9.5 * cm, 4.0 * cm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), secondary), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (-1, 0), (-1, 0), "RIGHT"), ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.extend([header, Spacer(1, 0.45 * cm)])

    info_data = [[
        Paragraph(f"<b>ÉMETTEUR</b><br/>{clinic_name}<br/>{clinic.get('address', '')}<br/>{clinic.get('phone', '')}", styles["Meta"]),
        Paragraph(f"<b>CLIENT</b><br/>{patient.prenom} {patient.nom}<br/>{patient.adresse or ''}<br/>{patient.telephone or ''}", styles["Meta"]),
    ]]
    info_table = Table(info_data, colWidths=[8.1 * cm, 8.1 * cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11), ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.extend([info_table, Spacer(1, 0.35 * cm)])

    meta = f"Date d'émission : {facture.date_emission}"
    if facture.date_echeance:
        meta += f"   •   Date d'échéance : {facture.date_echeance}"
    elements.extend([Paragraph(meta, styles["Meta"]), Spacer(1, 0.3 * cm)])

    table_data = [["Description", "Prix unitaire", "Qté", "Total HT"]]
    lignes = (facture.actes or []) + (facture.produits or [])
    for ligne in lignes:
        prix = Decimal(str(ligne.get("prix", 0)))
        qte = int(ligne.get("quantite", 1))
        table_data.append([Paragraph(str(ligne.get("description", "Sans description")), styles["Small"]), f"{prix:.2f} {currency_symbol}", str(qte), f"{prix * qte:.2f} {currency_symbol}"])
    table_data.append(["", "", "Sous-total HT", f"{facture.sous_total:.2f} {currency_symbol}"])
    if facture.remise_globale_pct > 0:
        remise_montant = facture.sous_total * (facture.remise_globale_pct / Decimal("100"))
        table_data.append(["", "", f"Remise ({facture.remise_globale_pct}%)", f"-{remise_montant:.2f} {currency_symbol}"])
    tva_pct = (facture.taux_tva * 100).quantize(Decimal("1"))
    table_data.extend([["", "", f"TVA ({tva_pct}%)", f"{facture.montant_tva:.2f} {currency_symbol}"], ["", "", "TOTAL TTC", f"{facture.total_ttc:.2f} {currency_symbol}"]])
    items_table = Table(table_data, colWidths=[8.2 * cm, 3.1 * cm, 1.5 * cm, 3.5 * cm], repeatRows=1)
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), primary), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (2, 1), (2, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -5), 0.45, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -5), [colors.white, colors.HexColor("#F8FAFC")]),
        ("BACKGROUND", (2, -1), (-1, -1), primary), ("TEXTCOLOR", (2, -1), (-1, -1), colors.white),
        ("FONTNAME", (2, -1), (-1, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.extend([items_table, Spacer(1, 0.45 * cm)])
    status_label = "PAYÉE" if facture.statut == "payee" else facture.statut.upper()
    elements.append(Paragraph(f"<b>Statut :</b> {status_label}   •   <b>Mode :</b> {facture.mode_paiement or '—'}", styles["Meta"]))
    if facture.notes:
        elements.extend([Spacer(1, 0.25 * cm), Paragraph("<b>Notes</b>", styles["Meta"]), Paragraph(str(facture.notes), styles["Small"])])
    elements.extend([Spacer(1, 0.9 * cm), Paragraph("Merci pour votre confiance.", ParagraphStyle("Thanks", parent=styles["Normal"], alignment=1, textColor=primary, fontSize=10))])
    doc.build(elements, onFirstPage=draw_footer, onLaterPages=draw_footer)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
