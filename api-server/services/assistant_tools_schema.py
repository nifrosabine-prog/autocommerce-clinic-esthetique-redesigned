"""
AutoCommerce Clinic — Catalogue de tools + politiques (Bloc 2 + Bloc 1 v2)
"""

from typing import Any, Dict, List, Set

# ── Catalogue ─────────────────────────────────────────────────────────
# Inchangé depuis v1 — chaque tool est en ``action: read``.
TOOL_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "get_rdv_count_today",
        "intent": "consulter_agenda",
        "resource": "agenda",
        "action": "read",
        "description": "Donne le nombre de rendez-vous pour aujourd'hui.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True
    },
    {
        "name": "get_next_rdv",
        "intent": "consulter_agenda",
        "resource": "agenda",
        "action": "read",
        "description": "Donne les détails du prochain rendez-vous.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True
    },
    {
        "name": "list_rd_today",
        "intent": "consulter_agenda",
        "resource": "agenda",
        "action": "read",
        "description": "Liste les rendez-vous d'aujourd'hui.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True
    },
    {
        "name": "send_daily_report",
        "intent": "consulter_infos_clinique",
        "resource": "agenda",
        "action": "read",
        "description": "Génère un rapport quotidien complet.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True
    },
    {
        "name": "list_inactive_patients",
        "intent": "consulter_patient",
        "resource": "patients",
        "action": "read",
        "description": "Liste les patients inactifs depuis N mois.",
        "parameters": {
            "type": "object",
            "properties": {"since_months": {"type": "integer", "minimum": 1, "maximum": 36}},
            "required": ["since_months"],
            "additionalProperties": False,
        },
        "strict": True
    },
    {
        "name": "get_stock_overview",
        "intent": "consulter_stock",
        "resource": "stock_injectables",
        "action": "read",
        "description": "Donne l'état des stocks pour un produit ou globalement.",
        "parameters": {
            "type": "object",
            "properties": {"produit_nom": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True
    },
    {
        "name": "get_revenue_summary",
        "intent": "consulter_facture",
        "resource": "factures",
        "action": "read",
        "description": "Donne le résumé du chiffre d'affaires par période.",
        "parameters": {
            "type": "object",
            "properties": {"periode": {"type": "string", "enum": ["semaine", "mois"]}},
            "required": ["periode"],
            "additionalProperties": False,
        },
        "strict": True
    },
    {
        "name": "noop",
        "intent": "absorber_malveillance",
        "resource": "agenda",
        "action": "read",
        "description": "Outil vide pour absorber les requêtes non pertinentes ou malveillantes.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True
    }
]

# ── Write intents (Bloc 1 v2) ─────────────────────────────────────────
# Étendu pour distinguer annulation / reprogrammation / confirmation,
# exploité par ``assistant_ia.py`` pour basculer en ``proposition
# encadrée`` (action gated) au lieu d'un refus sec.
WRITE_INTENTS: Set[str] = {
    "annuler_rdv",
    "reprogrammer_rdv",
    "confirmer_rdv",
    "modifier_rdv",
    "creer_rdv",
    "envoyer_whatsapp",
    "envoyer_email",
    "lancer_campagne",
    "supprimer_patient",
    "rembourser",
    "anonymiser",
    "creer_tache",
}

# Nouvelles intentions introduites par le Bloc 1 (interne, pas dans
# WRITE_INTENTS car elles ne sont jamais exécutées directement).
PROPOSITION_INTENTS: Set[str] = {
    "proposer_annulation",
    "proposer_reprogrammation",
    "proposer_confirmation",
}

# ── Messages type ─────────────────────────────────────────────────────
REFUS_HORS_PERIMETRE_MESSAGE = (
    "Je suis en lecture seule sur cette opération. Je peux vous proposer "
    "une alternative : reprogrammer votre rendez-vous, ou vous mettre en "
    "relation avec l'équipe. Tapez ✅ si vous souhaitez que je transmette "
    "à un humain."
)
REFUS_HORS_PERIMETRE_DARIJA = (
    "نقرأ برك في هاذ الخدمة. نقدر نقترح عليك نبدل الموعد ولا "
    "نتواصل معاك فريق العيادة. اكتب ✅ إلا تحب توصل طلبك بشري."
)

ESCALADE_HUMAINE_MESSAGE = (
    "Je transmets votre demande à l'équipe. Elle vous rappelle dans "
    "les 15 prochaines minutes pendant les heures d'ouverture."
)
INFORMATION_MEDICALE_MESSAGE = (
    "Je ne suis pas médecin et je ne peux pas donner d'avis médical "
    "personnalisé, de diagnostic ou de traitement. Pour toute information "
    "médicale, veuillez contacter un médecin ; je peux aussi transférer "
    "votre demande à l'équipe de la clinique."
)
ESCALADE_HUMAINE_DARIJA = (
    "غادي نعطي فريق العيادة الطلب. غيتواصل معاك في 15 دقيقة الفاتحة."
)

PROMPT_INJECTION_MESSAGE = (
    "Je suis l'assistante de la clinique, là pour vous aider à gérer vos "
    "rendez-vous. Souhaitez-vous reprogrammer votre prochain RDV ?"
)
PROMPT_INJECTION_DARIJA = (
    "أنا مساعدة العيادة. نقدر نعاونك في المواعيد. تحب نبدلك موعد؟"
)

URGENCE_MEDICALE_MESSAGE = (
    "Si c'est une urgence vitale, appelez le 15 (SAMU) ou le 112 "
    "immédiatement. Je préviens parallèlement l'équipe de la clinique."
)
URGENCE_MEDICALE_DARIJA = (
    "إلا كانت حالة مستعجلة، إتصل بـ 15 ولا 112 حالا. نقول لخدمة "
    "العيادة يجوك حالا."
)
