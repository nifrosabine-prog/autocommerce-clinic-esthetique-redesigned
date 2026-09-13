"""Lina — réponse automatique aux PATIENTS sur le webhook WhatsApp réel.

CONTEXTE DU CORRECTIF
----------------------
Avant ce module, ``services/assistant_ia.py`` (Bloc 1-3, darija/médical/
escalade) n'était atteignable que via la route interne authentifiée
``POST /assistant/ask`` (voir ``api/v1/assistant.py``) — jamais depuis un
vrai message WhatsApp entrant. Le webhook réel (``middleware/
webhook_omnicanal.py``) ne routait vers un agent que les numéros
whitelistés (staff/direction, Bloc 9) ; un patient qui écrivait sur le
WhatsApp de la clinique était seulement enregistré dans l'inbox, sans
aucune réponse automatique de Lina.

``assistant_ia.handle_whatsapp_message`` ne peut pas être réutilisé tel
quel pour un patient : ``get_or_create_session`` lève une erreur si le
numéro n'est pas dans ``numeros_whitelist`` (table réservée au staff,
Bloc 9). Ce module fournit donc un chemin patient dédié, plus léger,
qui respecte les mêmes règles dures du Bloc 0 sans dépendre des tables
de session/commande réservées au staff : la traçabilité passe par les
lignes ``MessageOmnicanal`` (entrant/sortant), déjà persistées par
``services.omnicanal_service``.

RÈGLES DURES (Bloc 0, inchangées) :
  1. Jamais de diagnostic, prescription ou avis médical → escalade.
  2. Jamais de décision finale (RDV, envoi, commande...) → toute action
     est transmise à l'équipe humaine, jamais exécutée ici.
  3. Jamais de divulgation de prompt/secrets/données d'un autre patient.
  4. Le contenu du message patient est une DONNÉE, jamais un ordre
     (anti prompt-injection).
  5. Anti-hallucination : uniquement des données lues en base (le
     prochain RDV réel du patient), jamais un chiffre ou un fait inventé.
  6. Multilingue : français, darija, anglais, italien, allemand.
  7. Format court (max ~5 lignes), toujours orienté vers une validation
     humaine pour toute action.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.language import detect_language
from services.lina_i18n import normalize_lang, t
from services.medical_guard import escalation_message, is_medical_escalation

logger = logging.getLogger("lina_patient_reply")

# Réutilise les mêmes signaux d'injection que le Bloc 9 (assistant_security)
# pour rester cohérent, sans créer de dépendance croisée lourde.
_PROMPT_INJECTION_PATTERNS = (
    re.compile(r"ignore.{0,20}(instructions|prompt|r[eè]gles)", re.IGNORECASE),
    re.compile(r"tu es (maintenant|d[ée]sormais) un", re.IGNORECASE),
    re.compile(r"r[ée]v[èe]le.{0,15}(prompt|instructions|cl[ée]s?|secret)", re.IGNORECASE),
    re.compile(r"agis comme si", re.IGNORECASE),
    re.compile(r"forget (your|all) (instructions|rules)", re.IGNORECASE),
)

_NEXT_RDV_KEYWORDS = (
    "rdv", "rendez-vous", "rendez vous", "prochain", "quand",
    "موعد", "الجاي", "وقتاش", "appointment", "when", "appuntamento", "termin",
)

_GREETING_ONLY = re.compile(
    r"^\s*(bonjour|bonsoir|salut|coucou|hello|hi|hey|salam|سلام|أهلا|ciao|hallo)\s*[!.، ]*\s*$",
    re.IGNORECASE,
)


def _is_prompt_injection(text: str) -> bool:
    return any(p.search(text) for p in _PROMPT_INJECTION_PATTERNS)


async def _find_next_rdv(db: AsyncSession, patient_id: int, clinic_id: int) -> Optional[dict]:
    from datetime import datetime

    from models.database import ActeMedical, RendezVous, StatutRDV, Utilisateur

    rdv = await _find_next_rdv_row(db, patient_id, clinic_id)
    if not rdv:
        return None

    praticien = await db.get(Utilisateur, rdv.praticien_id)
    acte = await db.get(ActeMedical, rdv.acte_id) if rdv.acte_id else None
    return {
        "date": rdv.date_heure_debut.strftime("%d/%m/%Y à %H:%M"),
        "praticien": (f"{praticien.prenom} {praticien.nom}".strip() if praticien else "l'équipe"),
        "acte": acte.nom if acte else None,
    }


async def _find_next_rdv_row(db: AsyncSession, patient_id: int, clinic_id: int):
    """Variante de ``_find_next_rdv`` qui renvoie l'objet ``RendezVous`` brut
    (nécessaire pour la cascade d'annulation, qui a besoin du praticien_id
    et de la date réels, pas seulement du texte formaté)."""
    from datetime import datetime

    from models.database import RendezVous, StatutRDV

    stmt = (
        select(RendezVous)
        .where(
            RendezVous.patient_id == patient_id,
            RendezVous.clinic_id == clinic_id,
            RendezVous.date_heure_debut >= datetime.utcnow(),
            RendezVous.statut.in_([StatutRDV.PLANIFIE.value, StatutRDV.CONFIRME.value]),
        )
        .order_by(RendezVous.date_heure_debut.asc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def handle_patient_whatsapp(
    *,
    content: str,
    patient: Optional[object],
    clinic_id: int,
    db: AsyncSession,
) -> str:
    """Construit la réponse automatique de Lina pour un message PATIENT.

    ``patient`` est l'objet ``Patient`` déjà résolu par
    ``omnicanal_service.receive_message`` (peut être ``None`` si le
    numéro n'est pas encore rattaché à une fiche patient) — jamais
    re-cherché ici pour ne pas dupliquer la logique de matching.
    Ne lève jamais d'exception métier : en cas de doute, on transmet à
    l'équipe (règle 2 du Bloc 0) plutôt que de risquer une réponse
    incorrecte à un vrai patient.
    """
    text = (content or "").strip()
    lang = normalize_lang(detect_language(text))

    if not text:
        return t("greeting_unknown", lang)

    # Règle 4 — anti prompt-injection : le message est une donnée, jamais un ordre.
    if _is_prompt_injection(text):
        logger.warning("lina_patient_prompt_injection_detected clinic_id=%s", clinic_id)
        return t("prompt_injection_refusal", lang)

    # Règle 1 — zone médicale interdite → escalade immédiate, prioritaire sur tout le reste.
    if is_medical_escalation(text):
        return escalation_message(lang)

    prenom = getattr(patient, "prenom", None) if patient else None

    if _GREETING_ONLY.match(text):
        return (
            t("greeting_patient", lang, prenom=prenom)
            if prenom else t("greeting_unknown", lang)
        )

    text_lower = text.lower()

    # Lecture seule : prochain rendez-vous (aucune écriture, donnée réelle uniquement).
    if patient is not None and any(k in text_lower for k in _NEXT_RDV_KEYWORDS):
        try:
            next_rdv = await _find_next_rdv(db, patient.id, clinic_id)
        except Exception:
            logger.exception("lina_patient_next_rdv_lookup_failed clinic_id=%s", clinic_id)
            next_rdv = None
        if next_rdv:
            acte_suffix = (
                t("next_rdv_acte_suffix", lang, acte=next_rdv["acte"])
                if next_rdv.get("acte") else ""
            )
            return t(
                "next_rdv_found", lang,
                date=next_rdv["date"], praticien=next_rdv["praticien"],
                acte_suffix=acte_suffix,
            )
        return t("no_rdv", lang)

    # Réponse "NON" au rappel J-1 : jamais d'annulation ni de réaffectation
    # automatique (règle 2) — on cherche seulement, à titre de suggestion,
    # un autre patient dont le RDV pourrait être avancé sur ce créneau
    # probablement libéré, et on dépose une tâche pour l'assistante, qui
    # décide et agit elle-même. Le patient reçoit un accusé neutre.
    if patient is not None and re.fullmatch(r"non|no|لا", text_lower.strip(" !.،؟?")):
        try:
            next_rdv_row = await _find_next_rdv_row(db, patient.id, clinic_id)
            if next_rdv_row is not None:
                from services.remplacement_rdv import suggerer_cascade_apres_refus
                await suggerer_cascade_apres_refus(db, next_rdv_row, clinic_id=clinic_id)
        except Exception:
            logger.exception("lina_patient_cascade_suggestion_failed clinic_id=%s", clinic_id)
        return t("handoff_write_action", lang)

    # Demande d'action (annulation, reprogrammation, nouveau RDV...) : jamais
    # exécutée automatiquement pour un patient non whitelisté — transmise à
    # l'équipe, qui traite via le Bloc 2/3 avec confirmation encadrée.
    if any(k in text_lower for k in (
        "annul", "reprogram", "d[ée]plac", "déplac", "deplac", "confirm",
        "الغي", "بدل", "أكد",
    )):
        return t("handoff_write_action", lang)

    # Repli par défaut : rassurer, transmettre, proposer une suite — jamais
    # de contenu inventé (règle 5).
    return t("handoff_general", lang)
