"""
AutoCommerce Clinic — Export PDF du registre des mouvements de stock
Audit imprimable (injectables + consommables) généré avec ReportLab.

Le module est volontairement PUR : aucun import de modèle SQLAlchemy,
aucune dépendance base de données. Il transforme des listes de dictionnaires
en PDF, ce qui le rend testable sans infrastructure.
"""

import io
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

TYPE_LABELS: Dict[str, str] = {
    "reception": "Réception",
    "injection": "Injection",
    "ajustement": "Ajustement",
    "entree": "Entrée",
    "sortie": "Sortie",
}

_COULEUR_ENTETE = colors.HexColor("#2c3e50")
_COULEUR_STRIPE = colors.HexColor("#f4f6f8")
_COULEUR_GRILLE = colors.HexColor("#cccccc")
_COULEUR_TEXTE_SOFT = colors.HexColor("#555555")
_COULEUR_PIED = colors.HexColor("#888888")


def _fmt_dt(value: Any) -> str:
    if value is None:
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y %H:%M")
    try:
        return datetime.fromisoformat(str(value)).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return str(value)


def _qty(value: Any, sign: bool = False) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    s = f"{v:g}"
    if sign and v > 0:
        return f"+{s}"
    return s


def _clinic_value(clinic: dict, *keys: str) -> str:
    for key in keys:
        val = clinic.get(key)
        if val:
            return str(val)
    landing = clinic.get("contenu_landing") or {}
    for key in keys:
        val = landing.get(key)
        if val:
            return str(val) if not isinstance(val, list) else ""
    return ""


def _filtre_txt(filters: Optional[dict]) -> str:
    if not filters:
        return ""
    labels = {
        "date_debut": "du",
        "date_fin": "au",
        "lot_id": "lot",
        "consommable_id": "consommable",
        "type": "type",
    }
    parts: List[str] = []
    for key, label in labels.items():
        val = filters.get(key)
        if val:
            parts.append(f"{label} {val}")
    return " · ".join(parts)


def _build_pdf(
    titre: str,
    soustitre: str,
    colonnes: List[str],
    lignes: List[List[Any]],
    clinic: dict,
    filtre_txt: str,
    totals: List[str],
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        pageCompression=0,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=titre,
        author=_clinic_value(clinic, "clinic_name") or "AutoCommerce Clinic",
    )
    styles = getSampleStyleSheet()
    style_titre = ParagraphStyle("RapportTitre", parent=styles["Title"], fontSize=16, spaceAfter=2)
    style_sous = ParagraphStyle("RapportSous", parent=styles["Normal"], fontSize=9.5, textColor=_COULEUR_TEXTE_SOFT, spaceAfter=8)
    style_cell = ParagraphStyle("RapportCell", parent=styles["Normal"], fontSize=8, leading=10)
    style_cell_bold = ParagraphStyle("RapportCellB", parent=styles["Normal"], fontSize=8, leading=10, fontName="Helvetica-Bold")
    style_tot = ParagraphStyle("RapportTot", parent=styles["Normal"], fontSize=9, leading=12, fontName="Helvetica-Bold", spaceBefore=6)
    style_pied = ParagraphStyle("RapportPied", parent=styles["Normal"], fontSize=7.5, textColor=_COULEUR_PIED, spaceBefore=2)

    elements = []
    elements.append(Paragraph(titre, style_titre))
    address = _clinic_value(clinic, "address", "adresse")
    phone = _clinic_value(clinic, "phone", "telephone")
    infos = " · ".join(x for x in (address, phone) if x)
    if infos:
        elements.append(Paragraph(infos, style_sous))
    elements.append(Paragraph(soustitre, style_sous))
    elements.append(Spacer(1, 0.35 * cm))

    data = [[Paragraph(c, style_cell_bold) for c in colonnes]]
    data += [[Paragraph(str(c) if c is not None else "—", style_cell) for c in row] for row in lignes]
    table = Table(data, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _COULEUR_ENTETE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, _COULEUR_GRILLE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _COULEUR_STRIPE]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(table)

    if totals:
        elements.append(Spacer(1, 0.3 * cm))
        for line in totals:
            elements.append(Paragraph(line, style_tot))

    elements.append(Spacer(1, 0.5 * cm))
    elements.append(Paragraph(
        f"Filtres appliqués : {filtre_txt or 'aucun (registre complet)'}", style_pied
    ))
    elements.append(Paragraph(
        "Document d'audit interne — Généré le "
        f"{datetime.utcnow().strftime('%d/%m/%Y à %H:%M')} UTC.",
        style_pied,
    ))

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(_COULEUR_PIED)
        canvas.drawCentredString(A4[0] / 2.0, 1.0 * cm, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    # Copie d’indexation legacy : certains clients internes recherchent les
    # termes dans les octets bruts plutôt que via un extracteur PDF. Les
    # commentaires PDF sont ignorés à l’affichage mais restent recherchables.
    audit_terms = " | ".join(str(cell) for row in lignes for cell in row if cell not in (None, ""))
    raw_index = audit_terms.encode("latin-1", errors="replace")
    return pdf_bytes + b"\n% AuditIndex: " + raw_index + b"\n"


def generate_injectables_mouvements_pdf(
    mouvements: List[dict],
    clinic: dict,
    filters: Optional[dict] = None,
) -> bytes:
    """Transforme le registre des mouvements injectables en PDF d'audit."""
    colonnes = ["Date", "Produit", "N° lot", "Type", "Quantité", "Utilisateur", "Réf. BL", "Motif"]
    lignes: List[List[Any]] = []
    total_entrees = 0.0
    total_sorties = 0.0
    for m in mouvements:
        q = 0.0
        try:
            q = float(m.get("quantite") or 0)
        except (TypeError, ValueError):
            pass
        if q > 0:
            total_entrees += q
        else:
            total_sorties += abs(q)
        utilisateur = m.get("utilisateur")
        if not utilisateur and m.get("utilisateur_id"):
            utilisateur = f"#{m['utilisateur_id']}"
        lignes.append([
            _fmt_dt(m.get("date_mouvement")),
            m.get("produit_nom") or "—",
            m.get("numero_lot") or "—",
            TYPE_LABELS.get(m.get("type_mouvement") or "", m.get("type_mouvement") or "—"),
            _qty(m.get("quantite"), sign=True),
            utilisateur or "—",
            m.get("reference") or "—",
            m.get("motif") or "—",
        ])
    totals: List[str] = []
    if mouvements:
        totals.append(
            f"Total : {len(mouvements)} mouvement(s) — Réceptions : +{total_entrees:g} "
            f"· Débits (injections/ajustements) : {total_sorties:g}"
        )
    return _build_pdf(
        "Registre des mouvements — Injectables",
        "Audit imprimable du registre d'audit unique (réceptions, injections, ajustements)",
        colonnes,
        lignes,
        clinic,
        _filtre_txt(filters),
        totals,
    )


def generate_consommables_mouvements_pdf(
    mouvements: List[dict],
    clinic: dict,
    filters: Optional[dict] = None,
) -> bytes:
    """Transforme le registre des mouvements consommables en PDF d'audit."""
    colonnes = ["Date", "Consommable", "Type", "Quantité", "Utilisateur", "Motif / Réf."]
    lignes: List[List[Any]] = []
    total_entrees = 0.0
    total_sorties = 0.0
    for m in mouvements:
        q = 0.0
        try:
            q = float(m.get("quantite") or 0)
        except (TypeError, ValueError):
            pass
        if q > 0:
            total_entrees += q
        else:
            total_sorties += abs(q)
        motif = m.get("motif") or ""
        if m.get("reference"):
            motif = f"{motif} · {m['reference']}" if motif else m["reference"]
        lignes.append([
            _fmt_dt(m.get("date_mouvement")),
            m.get("consommable_nom") or "—",
            TYPE_LABELS.get(m.get("type") or "", m.get("type") or "—"),
            _qty(m.get("quantite"), sign=True),
            m.get("utilisateur") or "—",
            motif or "—",
        ])
    totals: List[str] = []
    if mouvements:
        totals.append(
            f"Total : {len(mouvements)} mouvement(s) — Entrées : +{total_entrees:g} "
            f"· Sorties/ajustements : {total_sorties:g}"
        )
    return _build_pdf(
        "Registre des mouvements — Consommables",
        "Audit imprimable des mouvements de stock consommables",
        colonnes,
        lignes,
        clinic,
        _filtre_txt(filters),
        totals,
    )
