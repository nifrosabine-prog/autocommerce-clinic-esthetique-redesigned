"""
AutoCommerce Clinic — Outils agent "Lina" (bloc 4, 5, 10 des prompts).

Ces fonctions comblent les outils marqués « À CRÉER » dans l'annexe des
prompts Lina. Elles suivent la même règle dure que le reste du runtime :
- lecture seule ou brouillon uniquement ;
- aucune action qui modifie un état sensible (aucune publication, aucune
  commande, aucun envoi) n'est exposée à l'agent ici — `publier_post`
  reste volontairement absent du registre d'outils agent : la publication
  ne peut être déclenchée que par un humain via la route REST dédiée ;
- aucun score ou chiffre inventé : tout est calculé depuis des données
  réellement chargées, jamais un placeholder LLM.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

# ─── Bloc 4 — Sentiment client (heuristique, sans dépendance ML) ──────────

_MOTS_POSITIFS = {
    "merci", "super", "excellent", "parfait", "content", "contente",
    "satisfait", "satisfaite", "ravi", "ravie", "génial", "top",
    "recommande", "professionnel", "professionnelle", "gentil", "gentille",
    "agréable", "bravo", "impeccable",
    # darija (translittéré)
    "mzyan", "mezian", "zwina", "zwin", "chokran", "hamdoullah", "wa3er",
}

_MOTS_NEGATIFS = {
    "déçu", "déçue", "mauvais", "mauvaise", "nul", "horrible", "attente",
    "annulé", "annulée", "cher", "douleur", "mal", "problème", "erreur",
    "insatisfait", "insatisfaite", "colère", "inadmissible", "scandaleux",
    "jamais", "décevant", "retard",
    "khayb", "mamzyanch", "makayench", "mochkil",
}

_URGENCE_MOTS = {"urgence", "urgent", "grave", "hôpital", "hopital", "sang", "douleur intense"}


def _tokenize(texte: str) -> list[str]:
    return re.findall(r"[a-zàâäéèêëïîôöùûüç]+", (texte or "").lower())


def _score_texte(texte: str) -> tuple[str, float, bool]:
    """Retourne (sentiment, confiance, urgence_detectee) à partir de compteurs
    de mots — déterministe, pas de score inventé par un LLM."""
    mots = _tokenize(texte)
    if not mots:
        return "neutre", 0.0, False
    pos = sum(1 for m in mots if m in _MOTS_POSITIFS)
    neg = sum(1 for m in mots if m in _MOTS_NEGATIFS)
    urgence = any(u in (texte or "").lower() for u in _URGENCE_MOTS)
    total = pos + neg
    if total == 0:
        return "neutre", 0.0, urgence
    if pos > neg:
        return "positif", round(pos / max(total, 1), 2), urgence
    if neg > pos:
        return "negatif", round(neg / max(total, 1), 2), urgence
    return "neutre", 0.5, urgence


async def analyze_sentiment(
    db: AsyncSession, current_user: dict, plateforme: Optional[str] = None,
) -> dict[str, Any]:
    """Bloc 4 — classe le ton des derniers messages omnicanal et avis.

    Lecture seule : aucune écriture, aucune réponse envoyée. Le score est
    une classification déterministe par mots-clés (FR + darija courants),
    jamais un chiffre inventé.
    """
    clinic_id = current_user.get("clinic_id")
    if not isinstance(clinic_id, int) or clinic_id <= 0:
        return {"error": "Contexte clinique requis."}

    from services.social_crm import list_messages
    from services.reputation import get_avis

    messages = await list_messages(db, plateforme=plateforme, clinic_id=clinic_id)
    avis = await get_avis(db, plateforme=plateforme, clinic_id=clinic_id)

    resultats: list[dict[str, Any]] = []
    alertes: list[dict[str, Any]] = []

    for m in messages[:50]:
        if getattr(m, "direction", None) != "entrant":
            continue
        sentiment, confiance, urgence = _score_texte(getattr(m, "contenu", ""))
        entry = {
            "source": "message",
            "id": m.id,
            "contact_id": getattr(m, "contact_id", None),
            "patient_id": getattr(m, "patient_id", None),
            "sentiment": sentiment,
            "confiance": confiance,
            "extrait": (getattr(m, "contenu", "") or "")[:140],
        }
        resultats.append(entry)
        if sentiment == "negatif" or urgence:
            alertes.append({**entry, "urgence": urgence})

    for a in avis[:50]:
        sentiment, confiance, urgence = _score_texte(getattr(a, "texte", ""))
        note = getattr(a, "note", None)
        # Une note basse (<=2/5) est un signal fort, indépendant du texte.
        if isinstance(note, int) and note <= 2:
            sentiment = "negatif"
        entry = {
            "source": "avis",
            "id": a.id,
            "plateforme": getattr(a, "plateforme", None),
            "note": note,
            "sentiment": sentiment,
            "confiance": confiance,
            "extrait": (getattr(a, "texte", "") or "")[:140],
        }
        resultats.append(entry)
        if sentiment == "negatif" or urgence:
            alertes.append({**entry, "urgence": urgence})

    return {
        "clinic_id": clinic_id,
        "total_analyse": len(resultats),
        "resultats": resultats,
        "alertes_a_traiter": alertes,
        "methode": "heuristique_mots_cles_fr_darija",
    }


# ─── Bloc 5 — Proposition de dispatching (lecture seule) ──────────────────

_JOURS_FR = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]


async def propose_dispatch(
    db: AsyncSession, current_user: dict, period_days: int = 30,
) -> dict[str, Any]:
    """Bloc 5 — croise créneaux sous-utilisés et absentéisme pour proposer
    des pistes de réorganisation. Ne modifie rien : uniquement des
    propositions textuelles numérotées, à valider par la directrice via
    `PATCH /rdv/{id}/replanifier`.
    """
    clinic_id = current_user.get("clinic_id")
    if not isinstance(clinic_id, int) or clinic_id <= 0:
        return {"error": "Contexte clinique requis."}
    if current_user.get("role") not in ("directrice", "admin", "assistante"):
        return {"error": "Accès réservé à l'équipe d'organisation."}

    from services.business_intelligence import BusinessIntelligenceService
    from services.dashboard_ia import DashboardIAService

    slots = await BusinessIntelligenceService.get_underutilized_slots(
        db, clinic_id=clinic_id, period_days=period_days,
    )
    absents = await DashboardIAService.get_absent_patients(
        db, clinic_id=clinic_id, days=period_days,
    )

    propositions: list[str] = []
    for s in slots.get("underutilized_slots", [])[:5]:
        jour = _JOURS_FR[s["weekday"]] if 0 <= s["weekday"] <= 6 else "?"
        propositions.append(
            f"Créneau {jour} {s['hour']}h sous-utilisé ({s['rdv_count']} RDV sur "
            f"{period_days}j) — envisager d'y déplacer un patient en attente "
            f"ou de le proposer en priorité pour une relance."
        )
    total_absents = absents.get("total_absent_patients", 0)
    if total_absents:
        propositions.append(
            f"{total_absents} patient(s) sans visite depuis {period_days}j — "
            f"proposer une relance ciblée (voir bloc 3, brouillon uniquement)."
        )

    return {
        "clinic_id": clinic_id,
        "period_days": period_days,
        "underutilized_slots": slots.get("underutilized_slots", []),
        "absent_patients_count": total_absents,
        "propositions": propositions,
        "note": "Aucune modification appliquée — propositions à valider par la directrice.",
    }


# ─── Bloc 10 — Publications réseaux sociaux (brouillon uniquement) ────────

_PLATEFORMES_SOCIAL_VALIDES = {"instagram", "facebook", "tiktok"}

# Conseils déclaratifs (documentation publique des plateformes), jamais un
# score inventé ni une garantie de portée — uniquement des repères de
# format que l'équipe peut suivre ou ignorer avant de publier elle-même.
_HASHTAG_RE = re.compile(r"#\w+")


def _social_recommendation_hints(plateforme: str, contenu: str) -> dict[str, Any]:
    longueur = len(contenu)
    nb_hashtags = len(_HASHTAG_RE.findall(contenu))
    a_media = None  # renseigné par l'appelant si besoin, non déterminable ici

    if plateforme == "tiktok":
        conseils = [
            "Format vidéo courte prioritaire (algorithme TikTok = rétention/complétion, pas le texte seul).",
            "Légende courte (1-2 phrases) + 3 à 5 hashtags ciblés, pas de mur de hashtags.",
            "3 premières secondes déterminantes : accroche visuelle avant le texte.",
        ]
        if nb_hashtags > 6:
            conseils.append("Trop de hashtags pour TikTok : réduire à 3-5 pertinents.")
    elif plateforme == "instagram":
        conseils = [
            "Légende avec accroche dans les 125 premiers caractères (coupure avant « plus »).",
            "5 à 15 hashtags de niche plutôt que des hashtags génériques très saturés.",
            "Un visuel net (carré ou 4:5) favorise davantage l'affichage que le texte seul.",
        ]
        if nb_hashtags > 20:
            conseils.append("Trop de hashtags pour Instagram (max recommandé ~30, idéal ~5-15).")
    elif plateforme == "facebook":
        conseils = [
            "Peu ou pas de hashtags (l'algorithme Facebook les valorise moins qu'Instagram).",
            "Légende plus longue tolérée, mais les 3 premières lignes doivent donner l'essentiel.",
            "Poser une question ou un CTA clair favorise les commentaires (signal fort pour l'algorithme).",
        ]
        if nb_hashtags > 3:
            conseils.append("Beaucoup de hashtags pour Facebook : privilégier 0 à 2.")
    else:
        conseils = []

    if longueur > 2200:
        conseils.append("Légende très longue : risque de troncature selon la plateforme.")

    return {
        "plateforme": plateforme,
        "longueur_caracteres": longueur,
        "nb_hashtags_detectes": nb_hashtags,
        "conseils_algorithme": conseils,
        "avertissement": "Repères de format publics, pas une garantie de portée ni un score mesuré.",
    }


async def create_social_post_draft(
    db: AsyncSession, current_user: dict,
    plateforme: str, contenu: str,
    media_url: Optional[str] = None,
    date_publication_prevue: Optional[str] = None,
) -> dict[str, Any]:
    """Bloc 10 — crée UNIQUEMENT un brouillon (jamais publié par l'agent).

    Volontairement, `publier_post` n'est pas exposé comme outil agent :
    la publication reste un clic humain sur `POST /social/posts/{id}/publier`.
    """
    clinic_id = current_user.get("clinic_id")
    if not isinstance(clinic_id, int) or clinic_id <= 0:
        return {"error": "Contexte clinique requis."}
    plateforme_norm = (plateforme or "").strip().lower()
    if plateforme_norm not in _PLATEFORMES_SOCIAL_VALIDES:
        return {"error": f"Plateforme non supportée : {plateforme}. "
                          f"Attendu : {sorted(_PLATEFORMES_SOCIAL_VALIDES)}"}
    if not contenu or not contenu.strip():
        return {"error": "Contenu vide."}
    if any(mot in contenu.lower() for mot in ("guéri", "guérison garantie", "sans risque", "miracle")):
        return {"error": "Contenu refusé : promesse de résultat médical interdite dans une publication."}

    from services.social_crm import create_post

    data = {
        "plateforme": plateforme_norm,
        "contenu": contenu,
        "media_url": media_url,
        # La date n'est qu'indicative : create_post ne déclenche rien
        # automatiquement (aucun scheduler actif — voir annexe Bloc 10).
        "date_publication_prevue": date_publication_prevue,
    }
    try:
        post = await create_post(data, created_by=current_user["id"], db=db, clinic_id=clinic_id)
    except ValueError as e:
        return {"error": str(e)}
    return {
        "id": post.id,
        "statut": post.statut,
        "plateforme": post.plateforme,
        "note": "Brouillon créé. Publication réservée à un humain via l'interface.",
        "recommandations_format": _social_recommendation_hints(plateforme_norm, contenu),
    }


async def list_social_posts_tool(
    db: AsyncSession, current_user: dict,
    plateforme: Optional[str] = None, statut: Optional[str] = None,
) -> dict[str, Any]:
    clinic_id = current_user.get("clinic_id")
    if not isinstance(clinic_id, int) or clinic_id <= 0:
        return {"error": "Contexte clinique requis."}

    from services.social_crm import list_posts

    posts = await list_posts(db, plateforme=plateforme, statut=statut, clinic_id=clinic_id)
    return {
        "clinic_id": clinic_id,
        "total": len(posts),
        "posts": [
            {"id": p.id, "plateforme": p.plateforme, "statut": p.statut,
             "date_publication_prevue": p.date_publication_prevue,
             "contenu_extrait": (p.contenu or "")[:100]}
            for p in posts
        ],
    }
