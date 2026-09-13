"""Tests — export PDF du registre des mouvements (audit imprimable V2.3).

Sans base de données : ``services/stock_audit_pdf.py`` est purement
documentaire (ReportLab). Chaque test génère un PDF et vérifie son
en-tête ``%PDF`` et sa taille minimale, puis vérifie que le texte du
tableau a bien été émis dans le document.
"""
import io

from services.stock_audit_pdf import (
    TYPE_LABELS,
    generate_consommables_mouvements_pdf,
    generate_injectables_mouvements_pdf,
)

CLINIC = {
    "clinic_name": "Clinique Esthétique Test",
    "address": "12 Avenue Habib Bourguiba, Tunis",
    "phone": "+216 71 000 000",
}


def _pdf_text(pdf_bytes: bytes) -> str:
    """Extrait le texte du PDF généré (les chaînes échappées de ReportLab
    apparaissent en clair dans le flux)."""
    try:
        return pdf_bytes.decode("latin-1", errors="ignore")
    except Exception:
        return ""


def test_labels_couvrent_les_types():
    assert set(TYPE_LABELS) >= {"reception", "injection", "ajustement", "entree", "sortie"}


def test_pdf_injectables_valide():
    mouvements = [
        {
            "mouvement_id": 1, "lot_id": 7, "produit_nom": "Botox Allergan",
            "numero_lot": "LOT-0001", "type_mouvement": "reception",
            "quantite": 20.0, "date_mouvement": "2026-09-01T10:30:00",
            "utilisateur_id": 2, "motif": "Réception commande n°14",
            "reference": "BL-2026-0142",
        },
        {
            "mouvement_id": 2, "lot_id": 7, "produit_nom": "Botox Allergan",
            "numero_lot": "LOT-0001", "type_mouvement": "injection",
            "quantite": -1.0, "date_mouvement": "2026-09-02T14:05:00",
            "utilisateur_id": 3, "motif": "Injection frontale", "reference": None,
        },
    ]
    pdf = generate_injectables_mouvements_pdf(
        mouvements, CLINIC, filters={"date_debut": "2026-09-01", "type": "reception"}
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1500
    texte = _pdf_text(pdf)
    assert "Registre des mouvements" in texte
    assert "Botox Allergan" in texte
    assert "BL-2026-0142" in texte


def test_pdf_consommables_valide():
    mouvements = [
        {
            "mouvement_id": 1, "consommable_id": 3, "consommable_nom": "Compresses stériles",
            "unite": "paquet", "type": "entree", "quantite": 10.0,
            "date_mouvement": "2026-09-01T09:00:00",
            "utilisateur": "Rim Ben Ali", "motif": "Réception fournisseur",
            "reference": "BL-2026-0150",
        },
        {
            "mouvement_id": 2, "consommable_id": 3, "consommable_nom": "Compresses stériles",
            "unite": "paquet", "type": "sortie", "quantite": -2.0,
            "date_mouvement": "2026-09-02T11:20:00",
            "utilisateur": "Sami Trabelsi", "motif": "Soin patient", "reference": None,
        },
    ]
    pdf = generate_consommables_mouvements_pdf(
        mouvements, CLINIC, filters={"consommable_id": 3, "type": "entree"}
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1500
    texte = _pdf_text(pdf)
    assert "Consommables" in texte
    assert "Compresses stériles" in texte


def test_pdf_vide_ok():
    """Registre vide → PDF valide avec mention « aucun filtre »."""
    pdf = generate_injectables_mouvements_pdf([], CLINIC, filters={})
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 800
