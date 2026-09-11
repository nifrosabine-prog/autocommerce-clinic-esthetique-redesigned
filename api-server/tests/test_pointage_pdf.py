from datetime import date, datetime

from api.v1.pointage import PointageReportItem, UserReport, _render_attendance_pdf


def test_render_attendance_pdf_generates_a_valid_pdf_document():
    report = UserReport(
        utilisateur_id=42,
        nom_complet="Utilisateur Synthétique",
        total_minutes=125,
        details=[
            PointageReportItem(
                date=date(2026, 8, 26),
                debut=datetime(2026, 8, 26, 8, 30),
                fin=datetime(2026, 8, 26, 10, 35),
                duree_minutes=125,
            )
        ],
    )

    pdf = _render_attendance_pdf(report, date(2026, 8, 1), date(2026, 8, 31))

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1_000
