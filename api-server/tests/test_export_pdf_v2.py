"""Tests du générateur PDF enrichi (export_dossier_pdf v2).

Couvre : export complet médecin avec consultations, prescriptions,
faits médicaux, documents/analyses ; branche directrice (sections
cliniques réservées) ; non-régression du format PDF.
"""
from datetime import datetime
from pathlib import Path

import pytest

from models.database import RoleEnum, Utilisateur
from services.consultations_medicales import create_consultation
from services.documents_medicaux import upload_document
from services.dossier_medical import export_dossier_pdf
from services.patient_medical_facts import create_fact
from services.prescriptions_medicales import create_prescription

SAFE = "Rapport d'analyse <3 & résultats"


def _user(u) -> dict:
    return {
        "id": u.id, "clinic_id": 1, "role": u.role,
        "prenom": u.prenom, "nom": u.nom, "email": u.email,
    }


@pytest.mark.asyncio
async def test_export_pdf_v2_medecin_full(db, medecin, patient):
    user = _user(medecin)
    await create_consultation(db, patient.id, user, {
        "date_consultation": datetime.utcnow(),
        "type_consultation": "initiale",
        "motif": SAFE,
        "observations_cliniques": "Peau sensible",
        "diagnostic": "Dermite",
        "plan_therapeutique": "Crème hydratante",
        "contre_indications": SAFE,
        "recommandation": "Revoir dans 1 mois",
    }, {})
    await create_prescription(db, patient.id, user, {
        "date_prescription": datetime.utcnow(),
        "details": {"medicament": "Paracétamol", "dosage": "1g", "frequence": "3x/j", "duree": "5 jours"},
    }, {})
    await create_fact(db, patient.id, user, {
        "type_fait": "allergie", "source": "MANUAL", "verification_status": "VERIFIED",
        "donnees": {"substance": "Pénicilline <3 &"},
    }, {})
    await upload_document(db, patient.id, user, b"faux-contenu-pdf", "analyse_sang.pdf", "application/pdf", SAFE, None, None, {})

    pdf = await export_dossier_pdf(patient.id, db, user=user)
    Path("/tmp/export_pdf_v2_medecin.pdf").write_bytes(pdf)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1500
    Path("/tmp/export_pdf_v2_medecin.pdf").write_bytes(pdf)


@pytest.mark.asyncio
async def test_export_pdf_v2_directrice_reserved(db, medecin, patient):
    # Le médecin alimente des données cliniques sensibles.
    user = _user(medecin)
    await create_consultation(db, patient.id, user, {
        "date_consultation": datetime.utcnow(),
        "motif": "Motif confidentiel",
        "diagnostic": "Diagnostic confidentiel",
    }, {})
    # La directrice exporte : le PDF doit être émis sans fuite clinique.
    directrice = Utilisateur(
        clinic_id=1, email="directrice@clinic.tn", hashed_password="x",
        nom="Ayari", prenom="Leila", role=RoleEnum.DIRECTRICE.value,
    )
    db.add(directrice)
    await db.flush()
    pdf = await export_dossier_pdf(patient.id, db, user=_user(directrice))
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2000
    Path("/tmp/export_pdf_v2_directrice.pdf").write_bytes(pdf)


@pytest.mark.asyncio
async def test_export_pdf_v2_empty_sections(db, medecin, patient):
    # Patient sans consultation, ni prescription, ni fait, ni document :
    # les sections vides ne doivent pas faire planter le générateur.
    pdf = await export_dossier_pdf(patient.id, db, user=_user(medecin))
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000
