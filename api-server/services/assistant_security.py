"""Services sécurité pour l'assistant WhatsApp et l'agent IA — v2 (Bloc 1).

Nouveautés Bloc 1 :

  • CANCELLATION_WINDOW_MINUTES (par défaut 240) — vérifie qu'une
    annulation de RDV est faite au moins 4 h à l'avance ; sinon
    l'assistant bascule en escalade humaine.

  • Fonctions HMAC :
        generate_confirmation_token(secret, action, target) -> short
        verify_confirmation_token(token, secret, action, target) -> bool
    Le token est utilisé pour valider la confirmation explicite du
    patient avant toute action d'écriture.

  • Listes de mots-clés exportées MEDICAL_DISTRESS_FR / DARIJA et
    PROMPT_INJECTION_PATTERNS, consommées par assistant_ia.py pour
    déclencher l'escalade ou le refus.

  • record_distress_escalation() : journalise explicitement une
    détresse médicale détectée (statut ``STATUT_URGENCE_MEDICALE``),
    pointe une notification humaine via audit medical.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.assistant_whitelist import lookup_whitelist, normalize_numero
from models.security import (
    AlerteSecurite,
    CommandeAssistant,
    ConfirmationSensible,
    NumeroWhitelist,
    SessionAssistant,
    StatutAlerteEnum,
    StatutConfirmationEnum,
    StatutSessionEnum,
    TypeAlerteEnum,
)

logger = logging.getLogger(__name__)

# ── Limites & fenêtres (Bloc 1 v2) ────────────────────────────────────
SESSION_TTL_MINUTES = 30
CONFIRMATION_TTL_MINUTES = 10
MAX_PAYLOAD_SIZE_KB = 32
RATE_LIMIT_PER_MINUTE = 5

# Fenêtre d'annulation autorisée par l'assistant — 4 h par défaut.
# Au-delà, l'assistant refuse et bascule en escalade humaine.
CANCELLATION_WINDOW_MINUTES = 240

# Statut d'audit spécifique aux détresses médicales (compat v1).
STATUT_URGENCE_MEDICALE = "urgence_medicale_escaladee"

# Outils d'écriture sensibles nécessitant une confirmation manuelle
# (conservé depuis v1).
SENSITIVE_WRITE_TOOLS: set[str] = {
    "send_whatsapp",
    "send_email",
    "delete_patient",
    "cancel_rdv",
    "delete_rdv",
    "update_rdv",
    "launch_campaign",
    "delete_invoice",
    "delete_facture",
    "annuler_commande",
}

# ── Mots-clés détresses médicales ─────────────────────────────────────
# FR — déclenche ``STATUT_URGENCE_MEDICALE`` immédiatement (avant rate limit).
MEDICAL_DISTRESS_FR: set[str] = {
    "douleur thoracique", "douleur poitrine", "mal à la poitrine",
    "je n'arrive plus à respirer", "je n'arrive pas à respirer",
    "je m'étouffe", "je suffoque", "je tombe dans les pommes",
    "je me suis évanoui", "saignement abondant", "saignement qui ne s'arrête pas",
    "j'ai perdu connaissance", "forte hémorragie",
    "j'ai fait un malaise", "j'ai eu un avc",
    "j'ai très mal", "j'ai mal au cœur",
    "j'ai peur de mourir", "je veux mourir", "suicide",
    "j'ai bu trop", "j'ai pris trop de médicaments", "surdosage", "overdose",
    "chute grave", "je suis tombé sur la tête", "traumatisme crânien",
    "convulsions", "convulsion", "je fais une crise",
    "visage qui gonfle", "gorge qui gonfle", "réaction allergique",
    "allergie sévère", "urticaire généralisée", "je ne vois plus",
    "vision trouble soudaine", "paralysé", "paralysie", "bouche de travers",
    "je n'arrive plus à parler", "perte de force", "vomissements incontrôlables",
    "fièvre très élevée", "infection qui s'aggrave", "pus abondant",
}

# Darija — équivalent pour la détection sur WhatsApp (racines par sous-chaîne).
MEDICAL_DISTRESS_DARIJA: set[str] = {
    "صدر", "قلب", "ما نجمش نتنفس", "نختنق", "ما نجمش نتنفس",
    "دم كثير", "نزيف", "سقطت", "وقعت", "وقعت على راسي",
    "أموت", "نموت", "نحب نموت", "ما عادش نقدر نتنفس", "نفس مقطوع",
    "وجيعة قوية", "وجيعة كبيرة", "وجيعة في صدري", "قلبي يوجع",
    "دم برشا", "الدم ما يوقفش", "ننزف", "دوخة قوية", "غشيان",
    "فقدت الوعي", "طيحت على راسي", "ضربة في الراس", "تشنج",
    "وجهي نفخ", "حلقي نفخ", "حساسية قوية", "ما نشوفش", "ما نجمش نهدر",
    "فمي معوج", "يدي ضعفت", "سخانة عالية برشا", "قيء متواصل",
}

# ── Patterns prompt injection ─────────────────────────────────────────
# Anti-extraction et anti-contournement système. La détection est
# volontairement conservative : on préfère classer un message
# légitime comme suspect plutôt que laisser passer une injection.
PROMPT_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(les\s+)?instructions\s+(pr[eé]c[eé]dentes|ant[eé]rieures|du\s+system|d[' ]syst[eè]me)", re.IGNORECASE),
    re.compile(r"oublie\s+(les\s+)?instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+\w+", re.IGNORECASE),
    re.compile(r"tu\s+es\s+(maintenant|d[eé]sormais)\s+", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if\s+you\s+are|a\s+)"),
    re.compile(r"reveal\s+(your|the)\s+(prompt|instructions?|system)", re.IGNORECASE),
    re.compile(r"montre\s+(ton|tes)\s+(prompt|instructions?)", re.IGNORECASE),
    re.compile(r"r[eé]v[eè]le\s+(ton|tes|le|les)\s+(prompt|instructions?|syst[eè]me)", re.IGNORECASE),
    re.compile(r"annonce\s+(ta|tes)\s+(règles|instructions?)", re.IGNORECASE),
    re.compile(r"system\s*:\s*ignore", re.IGNORECASE),
    re.compile(r"\bd[ée]but\s+prompt\b", re.IGNORECASE),
    re.compile(r"fin\s+prompt", re.IGNORECASE),
    re.compile(r"ignore(?:r)?\s+(?:tout|toutes|all)\s+(?:les\s+)?instructions", re.IGNORECASE),
    re.compile(r"(system|developer|assistant)\s*message\s*:", re.IGNORECASE),
    re.compile(r"(reveal|show|print|display|export).{0,40}(system prompt|hidden prompt|secret instructions)", re.IGNORECASE),
    re.compile(r"(jailbreak|dan|developer mode|mode développeur|mode sans restrictions)", re.IGNORECASE),
    re.compile(r"(base64|decode|d[eé]code).{0,30}(prompt|instruction|syst[eè]me)", re.IGNORECASE),
    re.compile(r"(ignore|oublie).{0,50}(s[eé]curit[eé]|r[eè]gles? m[eé]dicales?|garde.?fou)", re.IGNORECASE),
]


# ── Helpers HMAC (Bloc 1 v2) ──────────────────────────────────────────
def generate_confirmation_token(*, secret: str, action: str, target: str) -> str:
    """Génère un jeton court (12 chars) signé HMAC-SHA256.

    Le serveur conserve ``secret`` côté assistant_security ;
    l'utilisateur ne voit jamais le jeton complet — seul le composant
    qui orchestre les actions (appelé avec ``verify_confirmation_token``)
    peut le valider.
    """
    payload = f"{action}|{target}".encode("utf-8")
    key = (secret or "demo").encode("utf-8")
    digest = hmac.new(key, payload, hashlib.sha256).hexdigest()
    return digest[:12]


def verify_confirmation_token(
    *, token: str, secret: str, action: str, target: str,
) -> bool:
    """Vérifie un jeton généré par ``generate_confirmation_token``."""
    expected = generate_confirmation_token(
        secret=secret, action=action, target=target,
    )
    if not token or len(token) != len(expected):
        return False
    return hmac.compare_digest(expected, token)


def is_cancellation_window_ok(rdv_datetime: datetime, now: Optional[datetime] = None) -> bool:
    """Vrai si l'on est au moins CANCELLATION_WINDOW_MINUTES dans le futur."""
    if rdv_datetime is None:
        return False
    baseline = now or datetime.utcnow()
    if getattr(rdv_datetime, "tzinfo", None) is not None and getattr(baseline, "tzinfo", None) is None:
        rdv_datetime = rdv_datetime.replace(tzinfo=None)
    elif getattr(rdv_datetime, "tzinfo", None) is None and getattr(baseline, "tzinfo", None) is not None:
        baseline = baseline.replace(tzinfo=None)
    return (rdv_datetime - baseline).total_seconds() >= CANCELLATION_WINDOW_MINUTES * 60


# ── Helpers existants (conservés) ─────────────────────────────────────
def _now() -> datetime:
    return datetime.utcnow()


async def normalize_numero_via_middleware(numero: str) -> str:
    """Re-expose du helper middleware pour les imports décentralisés."""
    return await normalize_numero(numero)


async def check_rate_limit(numero: str, db: AsyncSession) -> bool:
    """Vérifie le rate limit (5 req/min) par numéro."""
    numero_norm = await normalize_numero(numero)
    one_minute_ago = _now() - timedelta(minutes=1)

    res = await db.execute(
        select(CommandeAssistant)
        .where(CommandeAssistant.numero == numero_norm)
        .where(CommandeAssistant.created_at >= one_minute_ago)
    )
    count = len(res.scalars().all())
    return count < RATE_LIMIT_PER_MINUTE


def sanitize_notes(text: str) -> str:
    """Sanitisation anti-injection pour les champs de notes."""
    if not text:
        return text
    text = re.sub(r"(?i)DROP\s+TABLE|DELETE\s+FROM|UPDATE\s+.*SET|INSERT\s+INTO", "", text)
    text = re.sub(r"<[^>]*>", "", text)
    return text.strip()


async def create_security_alert(
    db: AsyncSession,
    *,
    alert_type: str,
    description: str,
    severity: str = "moyenne",
    numero: Optional[str] = None,
    utilisateur_id: Optional[int] = None,
    details: Optional[dict[str, Any]] = None,
    clinic_id: int,
) -> AlerteSecurite:
    alerte = AlerteSecurite(
        clinic_id=clinic_id,
        type_alerte=alert_type,
        severite=severity,
        statut=StatutAlerteEnum.NOUVELLE.value,
        description=description,
        numero_concerne=await normalize_numero(numero) if numero else None,
        utilisateur_id=utilisateur_id,
        details_json=json.dumps(details, ensure_ascii=False)[:4000] if details else None,
    )
    db.add(alerte)
    await db.flush()
    return alerte


async def get_or_create_session(numero: str, current_user: dict[str, Any], db: AsyncSession) -> SessionAssistant:
    numero_norm = await normalize_numero(numero)
    res = await db.execute(
        select(SessionAssistant)
        .where(SessionAssistant.numero == numero_norm)
        .where(SessionAssistant.statut == StatutSessionEnum.ACTIVE.value)
        .order_by(SessionAssistant.created_at.desc())
    )
    session = res.scalar_one_or_none()
    now = _now()
    if session and session.expires_at > now and not session.revoked_at:
        session.derniere_activite = now
        session.nb_tours = (session.nb_tours or 0) + 1
        await db.flush()
        return session

    whitelist_row = await lookup_whitelist(numero_norm, db)
    if not whitelist_row:
        raise ValueError("Numéro whitelist introuvable")

    session = SessionAssistant(
        clinic_id=current_user["clinic_id"],
        whitelist_id=whitelist_row.id,
        utilisateur_id=current_user.get("id"),
        numero=numero_norm,
        token_session=secrets.token_urlsafe(32),
        expires_at=now + timedelta(minutes=SESSION_TTL_MINUTES),
        derniere_activite=now,
        nb_tours=1,
    )
    db.add(session)
    await db.flush()
    return session


async def rotate_whitelist_access(numero: str, revoked_by_id: int, db: AsyncSession, *, clinic_id: int) -> NumeroWhitelist:
    numero_norm = await normalize_numero(numero)
    row = await lookup_whitelist(numero_norm, db)
    if not row or row.clinic_id != clinic_id:
        raise ValueError("Numéro whitelist introuvable")
    row.last_key_rotation = _now()
    res = await db.execute(
        select(SessionAssistant)
        .where(SessionAssistant.whitelist_id == row.id)
        .where(SessionAssistant.statut == StatutSessionEnum.ACTIVE.value)
    )
    for sess in res.scalars().all():
        sess.statut = StatutSessionEnum.REVOKED.value
        sess.revoked_at = _now()
    await create_security_alert(
        db,
        alert_type=TypeAlerteEnum.TOKEN_ROTATION.value,
        description=f"Rotation d'accès WhatsApp pour {numero_norm}",
        severity="faible",
        numero=numero_norm,
        utilisateur_id=revoked_by_id,
        clinic_id=clinic_id,
    )
    await db.flush()
    return row


async def revoke_whitelist_access(numero: str, revoked_by_id: int, reason: str, db: AsyncSession, *, clinic_id: int) -> NumeroWhitelist:
    numero_norm = await normalize_numero(numero)
    res = await db.execute(select(NumeroWhitelist).where(NumeroWhitelist.numero == numero_norm, NumeroWhitelist.clinic_id == clinic_id))
    row = res.scalar_one_or_none()
    if not row:
        raise ValueError("Numéro whitelist introuvable")
    row.statut = "revoked"
    row.revoked_at = _now()
    row.revoked_by_id = revoked_by_id
    row.raison_revocation = reason[:300]
    sessions = await db.execute(
        select(SessionAssistant)
        .where(SessionAssistant.whitelist_id == row.id)
        .where(SessionAssistant.statut == StatutSessionEnum.ACTIVE.value)
    )
    for sess in sessions.scalars().all():
        sess.statut = StatutSessionEnum.REVOKED.value
        sess.revoked_at = _now()
    await db.flush()
    return row


async def log_assistant_command(
    db: AsyncSession,
    *,
    session: Optional[SessionAssistant],
    current_user: dict[str, Any],
    numero: str,
    type_commande: str,
    question: str,
    statut: str,
    reponse: Optional[str] = None,
    intent_detecte: Optional[str] = None,
    outil_appele: Optional[str] = None,
    raison_refus: Optional[str] = None,
    parametres: Optional[dict[str, Any]] = None,
    tool_payload: Optional[dict[str, Any]] = None,
    contexte: Optional[dict[str, Any]] = None,
    erreur_message: Optional[str] = None,
) -> CommandeAssistant:
    commande = CommandeAssistant(
        clinic_id=current_user["clinic_id"],
        session_id=session.id if session else None,
        whitelist_id=session.whitelist_id if session else current_user.get("whitelist_id"),
        utilisateur_id=current_user.get("id"),
        numero=await normalize_numero(numero),
        type_commande=type_commande,
        # Les contenus utilisateur/LLM ne sont pas des logs opérationnels :
        # ils sont volontairement omis pour éviter la persistance de PHI,
        # prompts, réponses ou secrets.
        question=None,
        reponse=None,
        intent_detecte=intent_detecte,
        outil_appele=outil_appele,
        role_applique=current_user.get("role"),
        statut=statut,
        raison_refus=raison_refus[:4000] if raison_refus else None,
        parametres_appel=(
            json.dumps({"keys": sorted(parametres.keys())}, ensure_ascii=False)
            if parametres else None
        ),
        tool_payload_json=None,
        contexte_json=(
            json.dumps({"keys": sorted(contexte.keys())}, ensure_ascii=False)
            if contexte else None
        ),
        erreur_message=(
            "Erreur assistant enregistrée (détail redacted)" if erreur_message else None
        ),
    )
    db.add(commande)
    await db.flush()
    return commande


# ── NOUVEAU — Bloc 1 : journalisation d'une détresse médicale ────────
async def record_distress_escalation(
    db: AsyncSession,
    *,
    current_user: dict[str, Any],
    numero: str,
    question_snippet: str,
    lang: str,
) -> AlerteSecurite:
    """Journalise une détresse patient détectée par l'assistant.

    Génère une alerte sécurité ``URGENCE_MEDICALE_ASSISTANT`` avec :

      - severity = "critique" (le dashboard directrice l'affiche en rouge)
      - details_json  = langue +50 premiers chars du message
      - statut = NOUVELLE pour tri immédiat

    La suite (notification humaine, appel SAMU) reste à la charge
    de l'orchestrateur (tâche Celery Beat dédiée).
    """
    numero_norm = await normalize_numero(numero)
    alerte = AlerteSecurite(
        clinic_id=current_user["clinic_id"],
        type_alerte=TypeAlerteEnum.URGENCE_MEDICALE_ASSISTANT.value if hasattr(TypeAlerteEnum, "URGENCE_MEDICALE_ASSISTANT") else "urgence_medicale",
        severite="critique",
        statut=StatutAlerteEnum.NOUVELLE.value,
        description=f"Détresse médicale détectée via assistant ({lang})",
        numero_concerne=numero_norm,
        utilisateur_id=current_user.get("id"),
        details_json=json.dumps(
            {"lang": lang, "snippet": question_snippet[:200]},
            ensure_ascii=False,
        ),
    )
    db.add(alerte)
    await db.flush()
    logger.warning(
        "Détresse médicale détectée via assistant — clinic_id=%s numero=%s lang=%s",
        current_user["clinic_id"], numero_norm, lang,
    )
    return alerte


async def create_confirmation(
    db: AsyncSession,
    *,
    session: SessionAssistant,
    current_user: dict[str, Any],
    numero: str,
    tool_name: str,
    tool_args: dict[str, Any],
    summary: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    lang: str = "fr",
) -> ConfirmationSensible:
    pending = await db.execute(
        select(ConfirmationSensible)
        .where(ConfirmationSensible.session_id == session.id)
        .where(ConfirmationSensible.statut == StatutConfirmationEnum.EN_ATTENTE.value)
        .order_by(ConfirmationSensible.created_at.desc())
    )
    for item in pending.scalars().all():
        item.statut = StatutConfirmationEnum.EXPIREE.value

    code = f"{secrets.randbelow(9000) + 1000}"
    confirmation = ConfirmationSensible(
        clinic_id=current_user["clinic_id"],
        utilisateur_id=current_user.get("id"),
        session_id=session.id,
        numero=await normalize_numero(numero),
        type_operation=tool_name,
        details_json=json.dumps({"tool_name": tool_name, "tool_args": tool_args, "summary": summary, "lang": lang}, ensure_ascii=False),
        resource_type=resource_type,
        resource_id=resource_id,
        code_confirmation=code,
        expires_at=_now() + timedelta(minutes=CONFIRMATION_TTL_MINUTES),
    )
    db.add(confirmation)
    await db.flush()
    return confirmation


async def get_pending_confirmation(session: SessionAssistant, db: AsyncSession) -> Optional[ConfirmationSensible]:
    res = await db.execute(
        select(ConfirmationSensible)
        .where(ConfirmationSensible.session_id == session.id)
        .where(ConfirmationSensible.statut == StatutConfirmationEnum.EN_ATTENTE.value)
        .order_by(ConfirmationSensible.created_at.desc())
    )
    confirmation = res.scalar_one_or_none()
    if not confirmation:
        return None
    if confirmation.expires_at <= _now():
        confirmation.statut = StatutConfirmationEnum.EXPIREE.value
        await db.flush()
        return None
    return confirmation


async def consume_confirmation_if_valid(
    message_text: str,
    *,
    session: SessionAssistant,
    current_user: dict[str, Any],
    db: AsyncSession,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    confirmation = await get_pending_confirmation(session, db)
    if not confirmation:
        return None, None

    try:
        stored = json.loads(confirmation.details_json or "{}")
    except Exception:
        stored = {}
    lang = stored.get("lang", "fr")

    text = (message_text or "").strip().lower()
    if text in {"non", "no", "annuler", "stop", "refuser"}:
        confirmation.statut = StatutConfirmationEnum.REFUSEE.value
        await set_session_context(session, db, None)
        await db.flush()
        return None, ("الطلب تلغى." if lang == "darija" else "Action annulée.")

    expected = confirmation.code_confirmation.lower()
    normalized = text.replace("confirmer", "").replace("confirm", "").strip()
    if normalized != expected:
        msg = (f"عندك طلب تأكيد معلق. اكتب CONFIRMER {confirmation.code_confirmation} ولا NON."
               if lang == "darija" else
               f"Confirmation en attente. Répondez CONFIRMER {confirmation.code_confirmation} ou NON.")
        return None, msg

    confirmation.statut = StatutConfirmationEnum.CONFIRMEE.value
    confirmation.confirme_at = _now()
    session.derniere_activite = _now()
    await db.flush()
    return stored, None


async def get_session_context(session: SessionAssistant) -> Optional[dict[str, Any]]:
    if not session or not session.contexte_json:
        return None
    try:
        return json.loads(session.contexte_json)
    except json.JSONDecodeError:
        return None


async def set_session_context(session: SessionAssistant, db: AsyncSession, context: Optional[dict[str, Any]]) -> None:
    session.contexte_json = json.dumps(context, ensure_ascii=False) if context else None
    session.derniere_activite = _now()
    await db.flush()
