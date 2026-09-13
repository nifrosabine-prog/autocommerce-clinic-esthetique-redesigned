"""AutoCommerce Clinic — Service Recrutement"""
from datetime import datetime
from typing import Optional
import re
from io import BytesIO
from pathlib import Path

from sqlalchemy import select

from config import get_settings
from core.llm_client import LLMUnavailable, get_llm_client
from models.database import (
    Candidature, HistoriqueCandidature, Poste, StatutCandidature, StatutPoste,
)

settings = get_settings()


def extraire_texte_document(content: bytes, suffix: str) -> str:
    """Extrait le texte d’un PDF ou DOCX, sans bloquer le recrutement en cas d’échec."""
    try:
        if suffix.lower() == ".pdf":
            from pypdf import PdfReader
            return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages).strip()
        if suffix.lower() == ".docx":
            from docx import Document
            return "\n".join(p.text for p in Document(BytesIO(content)).paragraphs).strip()
    except Exception:
        return ""
    return ""


async def create_poste(
    titre: str, description: Optional[str], db, clinic_id: int, cree_par_id: Optional[int] = None,
) -> Poste:
    poste = Poste(
        clinic_id=clinic_id, titre=titre, description=description,
        statut=StatutPoste.OUVERT.value, cree_par_id=cree_par_id,
    )
    db.add(poste)
    await db.flush()
    return poste


async def generer_annonce_ia(poste_id: int, db, clinic_id: int) -> str:
    """Rédige une proposition d'annonce sans la publier automatiquement."""
    poste = await db.scalar(select(Poste).where(Poste.id == poste_id, Poste.clinic_id == clinic_id))
    if not poste:
        raise ValueError("Poste non trouvé")
    llm = get_llm_client(settings)
    response = await llm.chat(
        [
            {"role": "system", "content": "Rédigez une annonce professionnelle pour une clinique esthétique, avec présentation, missions, profil recherché et invitation à candidater. N’inventez ni salaire, ni adresse, ni avantage. Ne publiez rien et ne contactez aucun candidat."},
            {"role": "user", "content": f"Titre : {poste.titre}\nDescription : {poste.description or 'Non précisée'}"},
        ],
        temperature=0.4,
        max_tokens=700,
        budget_subject=f"clinic:{clinic_id}:recrutement-annonce",
        budget_clinic_id=clinic_id,
    )
    if isinstance(response, LLMUnavailable):
        raise RuntimeError("La génération IA est indisponible pour le moment")
    return response.text.strip()


async def list_postes(
    db, clinic_id: int, statut: Optional[str] = None,
) -> list[Poste]:
    query = select(Poste).where(Poste.clinic_id == clinic_id)
    if statut:
        query = query.where(Poste.statut == statut)
    result = await db.execute(query.order_by(Poste.created_at.desc()))
    return list(result.scalars().all())


async def fermer_poste(poste_id: int, db, clinic_id: int) -> Poste:
    stmt = select(Poste).where(Poste.id == poste_id, Poste.clinic_id == clinic_id)
    result = await db.execute(stmt)
    poste = result.scalar_one_or_none()
    if not poste:
        raise ValueError("Poste non trouvé")
    poste.statut = StatutPoste.FERME.value
    poste.ferme_le = datetime.utcnow()
    await db.flush()
    return poste


async def analyser_cv_ia(
    candidature_id: int, db, clinic_id: int, texte_cv: Optional[str] = None,
) -> Candidature:
    """Analyse un CV par IA — fonctionnalité strictement optionnelle.

    Si le budget IA de la clinique est épuisé (ou l'IA désactivée/mal
    configurée), on ne lève jamais d'erreur bloquante : la candidature est
    marquée ``analyse_ia_statut = "indisponible"`` et reste pilotable à la
    main exactement comme avant. Le recrutement ne dépend jamais de l'IA.
    """
    stmt = select(Candidature).where(
        Candidature.id == candidature_id, Candidature.clinic_id == clinic_id,
    )
    result = await db.execute(stmt)
    candidature = result.scalar_one_or_none()
    if not candidature:
        raise ValueError("Candidature non trouvée")

    contenu = (texte_cv or "").strip()
    if not contenu:
        # Pas de texte de CV exploitable (juste un lien de fichier non
        # extrait, par ex.) : on repasse proprement en mode manuel plutôt
        # que d'échouer.
        candidature.analyse_ia_statut = "indisponible"
        candidature.analyse_ia_resume = (
            "Aucun texte de CV exploitable — poursuivez l'évaluation manuellement."
        )
        candidature.analyse_ia_le = datetime.utcnow()
        await db.flush()
        return candidature

    llm = get_llm_client(settings)
    response = await llm.chat(
        [
            {
                "role": "system",
                "content": (
                    "Vous assistez un service RH de clinique esthétique. Résumez ce CV en "
                    "3 phrases maximum : expérience pertinente, compétences clés, points "
                    "d'attention. Terminez par une ligne 'Score: N/100' estimant "
                    "l'adéquation générale. Ne donnez jamais de recommandation "
                    "d'embauche définitive — seulement une aide à la lecture."
                ),
            },
            {"role": "user", "content": contenu[:8000]},
        ],
        temperature=0.2,
        max_tokens=400,
        budget_subject=f"clinic:{clinic_id}:recrutement",
        budget_clinic_id=clinic_id,
    )

    if isinstance(response, LLMUnavailable):
        # Solde IA à zéro, IA désactivée, ou clé manquante : on ne bloque
        # jamais le recrutement, on repasse simplement la main à l'humain.
        candidature.analyse_ia_statut = "indisponible"
        candidature.analyse_ia_resume = (
            "Analyse IA indisponible pour le moment (quota ou configuration) — "
            "poursuivez l'évaluation manuellement."
        )
        candidature.analyse_ia_le = datetime.utcnow()
        await db.flush()
        return candidature

    texte = response.text.strip()
    score = None
    for ligne in texte.splitlines():
        match = re.search(r"score\s*[:：]?\s*(\d{1,3})(?:\s*/\s*100)?", ligne, re.IGNORECASE)
        if match:
            score = max(0, min(100, int(match.group(1))))
            break

    candidature.analyse_ia_statut = "terminee"
    candidature.analyse_ia_resume = texte
    candidature.analyse_ia_score = score
    candidature.analyse_ia_le = datetime.utcnow()
    await db.flush()
    return candidature


TRANSITIONS_VALIDES = {
    StatutCandidature.RECU.value: {StatutCandidature.EN_ETUDE.value, StatutCandidature.REFUSE.value},
    StatutCandidature.EN_ETUDE.value: {StatutCandidature.ENTRETIEN.value, StatutCandidature.REFUSE.value},
    StatutCandidature.ENTRETIEN.value: {StatutCandidature.ACCEPTE.value, StatutCandidature.REFUSE.value},
    StatutCandidature.ACCEPTE.value: set(),
    StatutCandidature.REFUSE.value: set(),
}


async def create_candidature(
    data: dict, db, clinic_id: int = 1, created_by_id: int | None = None,
) -> Candidature:
    poste_id = data.get("poste_id")
    poste_libelle = (data.get("poste") or "").strip()
    if poste_id is not None:
        poste = await db.scalar(
            select(Poste).where(Poste.id == poste_id, Poste.clinic_id == clinic_id)
        )
        if poste is None:
            raise ValueError("Poste non trouvé dans cette clinique")
        if poste.statut != StatutPoste.OUVERT.value:
            raise ValueError("Une candidature ne peut être rattachée qu'à un poste ouvert")
        poste_libelle = poste.titre
    if not poste_libelle:
        raise ValueError("Le poste est obligatoire")

    candidature = Candidature(
        clinic_id=clinic_id, poste=poste_libelle, poste_id=poste_id,
        nom_candidat=data["nom_candidat"].strip(), email=data["email"].strip().lower(),
        telephone=data.get("telephone"), cv_url=data.get("cv_url"),
        lettre_url=data.get("lettre_url"), statut=StatutCandidature.RECU.value,
    )
    db.add(candidature)
    await db.flush()
    db.add(HistoriqueCandidature(
        candidature_id=candidature.id, clinic_id=clinic_id,
        ancien_statut=None, nouveau_statut=StatutCandidature.RECU.value,
        change_par_id=created_by_id,
    ))
    return candidature


async def changer_statut(candidature_id: int, nouveau_statut: str, evaluateur_id: int, db,
                          notes_rh: Optional[str] = None, date_entretien: Optional[datetime] = None,
                          clinic_id: int | None = None) -> Candidature:
    stmt = select(Candidature).where(Candidature.id == candidature_id)
    if clinic_id is not None:
        stmt = stmt.where(Candidature.clinic_id == clinic_id)
    result = await db.execute(stmt)
    candidature = result.scalar_one_or_none()
    if not candidature:
        raise ValueError("Candidature non trouvée")

    autorises = TRANSITIONS_VALIDES.get(candidature.statut, set())
    if nouveau_statut not in autorises:
        raise ValueError(f"Transition invalide : {candidature.statut} → {nouveau_statut}")

    ancien_statut = candidature.statut
    candidature.statut = nouveau_statut
    candidature.evaluateur_id = evaluateur_id
    if notes_rh:
        candidature.notes_rh = notes_rh
    if date_entretien:
        candidature.date_entretien = date_entretien

    db.add(HistoriqueCandidature(
        candidature_id=candidature.id, clinic_id=candidature.clinic_id,
        ancien_statut=ancien_statut, nouveau_statut=nouveau_statut,
        notes_rh=notes_rh, date_entretien=date_entretien, change_par_id=evaluateur_id,
    ))
    await db.flush()
    return candidature


async def list_candidatures(db, statut: Optional[str] = None, poste: Optional[str] = None,
                       clinic_id: int | None = None) -> list[Candidature]:
    query = select(Candidature)
    if clinic_id is not None:
        query = query.where(Candidature.clinic_id == clinic_id)
    if statut:
        query = query.where(Candidature.statut == statut)
    if poste:
        query = query.where(Candidature.poste == poste)
    result = await db.execute(query.order_by(Candidature.created_at.desc()))
    return list(result.scalars().all())
