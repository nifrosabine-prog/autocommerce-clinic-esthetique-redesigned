"""Tests — services/recrutement.py"""
from unittest.mock import AsyncMock, patch

import pytest

from services.recrutement import (
    analyser_cv_ia,
    changer_statut,
    create_candidature,
    create_poste,
    fermer_poste,
    list_candidatures,
    list_postes,
)
from models.database import StatutCandidature, StatutPoste


@pytest.mark.asyncio
async def test_create_candidature_defaults_to_recu(db):
    c = await create_candidature({
        "poste": "Assistante médicale", "nom_candidat": "Salma Jendoubi", "email": "s@x.tn",
    }, db)
    assert c.statut == StatutCandidature.RECU.value


@pytest.mark.asyncio
async def test_changer_statut_valid_transition(db):
    c = await create_candidature({"poste": "Médecin", "nom_candidat": "X", "email": "x@x.tn"}, db)
    updated = await changer_statut(c.id, StatutCandidature.EN_ETUDE.value, evaluateur_id=1, db=db)
    assert updated.statut == StatutCandidature.EN_ETUDE.value


@pytest.mark.asyncio
async def test_changer_statut_rejects_invalid_transition(db):
    c = await create_candidature({"poste": "Médecin", "nom_candidat": "X", "email": "x@x.tn"}, db)
    with pytest.raises(ValueError, match="invalide"):
        await changer_statut(c.id, StatutCandidature.ACCEPTE.value, evaluateur_id=1, db=db)


@pytest.mark.asyncio
async def test_changer_statut_rejects_transition_from_terminal_state(db):
    c = await create_candidature({"poste": "Médecin", "nom_candidat": "X", "email": "x@x.tn"}, db)
    await changer_statut(c.id, StatutCandidature.REFUSE.value, evaluateur_id=1, db=db)
    with pytest.raises(ValueError, match="invalide"):
        await changer_statut(c.id, StatutCandidature.EN_ETUDE.value, evaluateur_id=1, db=db)


@pytest.mark.asyncio
async def test_changer_statut_unknown_id_raises(db):
    with pytest.raises(ValueError, match="non trouvée"):
        await changer_statut(999999, StatutCandidature.EN_ETUDE.value, evaluateur_id=1, db=db)


@pytest.mark.asyncio
async def test_list_candidatures_filters_by_poste(db):
    await create_candidature({"poste": "Médecin", "nom_candidat": "A", "email": "a@x.tn"}, db)
    await create_candidature({"poste": "Assistante", "nom_candidat": "B", "email": "b@x.tn"}, db)
    resultats = await list_candidatures(db, poste="Médecin")
    assert len(resultats) == 1
    assert resultats[0].nom_candidat == "A"


@pytest.mark.asyncio
async def test_create_poste_defaults_to_ouvert(db):
    p = await create_poste("Esthéticienne senior", "CDI temps plein", db, clinic_id=1)
    assert p.statut == StatutPoste.OUVERT.value
    assert p.titre == "Esthéticienne senior"


@pytest.mark.asyncio
async def test_fermer_poste_changes_statut(db):
    p = await create_poste("Réceptionniste", None, db, clinic_id=1)
    fermed = await fermer_poste(p.id, db, clinic_id=1)
    assert fermed.statut == StatutPoste.FERME.value
    assert fermed.ferme_le is not None


@pytest.mark.asyncio
async def test_fermer_poste_unknown_id_raises(db):
    with pytest.raises(ValueError, match="non trouvé"):
        await fermer_poste(999999, db, clinic_id=1)


@pytest.mark.asyncio
async def test_list_postes_filters_by_clinic(db):
    await create_poste("Poste clinique 1", None, db, clinic_id=1)
    await create_poste("Poste clinique 2", None, db, clinic_id=2)
    resultats = await list_postes(db, clinic_id=1)
    assert all(p.clinic_id == 1 for p in resultats)


@pytest.mark.asyncio
async def test_analyser_cv_ia_falls_back_to_manual_when_no_text(db):
    """Sans texte de CV exploitable, on repasse en mode manuel sans erreur."""
    c = await create_candidature(
        {"poste": "Assistante", "nom_candidat": "Y", "email": "y@x.tn"}, db,
    )
    result = await analyser_cv_ia(c.id, db, clinic_id=1, texte_cv=None)
    assert result.analyse_ia_statut == "indisponible"
    # Le dossier reste pilotable à la main malgré l'absence d'analyse IA.
    updated = await changer_statut(c.id, StatutCandidature.EN_ETUDE.value, evaluateur_id=1, db=db)
    assert updated.statut == StatutCandidature.EN_ETUDE.value


@pytest.mark.asyncio
async def test_analyser_cv_ia_falls_back_when_budget_exhausted(db):
    """Solde IA à zéro (LLMUnavailable) : jamais d'exception, jamais de blocage."""
    from core.llm_client import LLMUnavailable

    c = await create_candidature(
        {"poste": "Médecin", "nom_candidat": "Z", "email": "z@x.tn"}, db,
    )
    fake_client = AsyncMock()
    fake_client.chat = AsyncMock(
        return_value=LLMUnavailable("openai", "Quota IA dépassée")
    )
    with patch("services.recrutement.get_llm_client", return_value=fake_client):
        result = await analyser_cv_ia(
            c.id, db, clinic_id=1, texte_cv="Expérience de 5 ans en clinique esthétique.",
        )
    assert result.analyse_ia_statut == "indisponible"
    assert result.analyse_ia_score is None
    # Le recrutement continue normalement malgré l'IA indisponible.
    refused = await changer_statut(c.id, StatutCandidature.REFUSE.value, evaluateur_id=1, db=db)
    assert refused.statut == StatutCandidature.REFUSE.value


@pytest.mark.asyncio
async def test_analyser_cv_ia_parses_score_when_available(db):
    from core.llm_client import LLMResponse

    c = await create_candidature(
        {"poste": "Médecin", "nom_candidat": "W", "email": "w@x.tn"}, db,
    )
    fake_client = AsyncMock()
    fake_client.chat = AsyncMock(
        return_value=LLMResponse(
            text="Bon profil clinique.\nScore: 82/100", provider="openai", model="gpt-4o",
        )
    )
    with patch("services.recrutement.get_llm_client", return_value=fake_client):
        result = await analyser_cv_ia(
            c.id, db, clinic_id=1, texte_cv="Expérience de 5 ans en clinique esthétique.",
        )
    assert result.analyse_ia_statut == "terminee"
    assert result.analyse_ia_score == 82
