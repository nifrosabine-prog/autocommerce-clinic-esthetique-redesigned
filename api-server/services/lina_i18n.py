"""Lina — table de traduction centrale (Bloc 0 : « Langue »).

Le prompt racine (Bloc 0) impose : « tu réponds en français, et en darija
si le client écrit en darija ». Cette table étend la règle à l'anglais,
l'italien et l'allemand — déjà détectés par ``services.language`` mais
jamais utilisés pour construire une réponse en dehors du fr/darija.

Usage :
    from services.lina_i18n import t
    t("greeting_patient", lang, prenom="Sarah")

Toutes les clés doivent exister dans les 5 langues supportées ; un test
(``test_lina_i18n.py``) vérifie la complétude de la table pour éviter un
retour silencieux en français quand une clé est ajoutée en darija/fr
seulement.
"""
from __future__ import annotations

SUPPORTED_LANGS = ("fr", "darija", "en", "it", "de")

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "greeting_patient": {
        "fr": "Bonjour {prenom}, je suis Lina, l'assistante de la clinique. Comment puis-je vous aider ?",
        "darija": "أهلا {prenom}، أنا لينا، مساعدة العيادة. كيفاش نجم نعاونك ؟",
        "en": "Hello {prenom}, I'm Lina, the clinic's assistant. How can I help you?",
        "it": "Buongiorno {prenom}, sono Lina, l'assistente della clinica. Come posso aiutarla?",
        "de": "Hallo {prenom}, ich bin Lina, die Assistentin der Klinik. Wie kann ich Ihnen helfen?",
    },
    "greeting_unknown": {
        "fr": "Bonjour, je suis Lina, l'assistante de la clinique. Comment puis-je vous aider ?",
        "darija": "أهلا، أنا لينا، مساعدة العيادة. كيفاش نجم نعاونك ؟",
        "en": "Hello, I'm Lina, the clinic's assistant. How can I help you?",
        "it": "Buongiorno, sono Lina, l'assistente della clinica. Come posso aiutarla?",
        "de": "Hallo, ich bin Lina, die Assistentin der Klinik. Wie kann ich Ihnen helfen?",
    },
    "next_rdv_found": {
        "fr": "Votre prochain rendez-vous est le {date} avec {praticien}{acte_suffix}.",
        "darija": "الموعد الجاي متاعك نهار {date} مع {praticien}{acte_suffix}.",
        "en": "Your next appointment is on {date} with {praticien}{acte_suffix}.",
        "it": "Il suo prossimo appuntamento è il {date} con {praticien}{acte_suffix}.",
        "de": "Ihr nächster Termin ist am {date} bei {praticien}{acte_suffix}.",
    },
    "next_rdv_acte_suffix": {
        "fr": " pour {acte}",
        "darija": " باش تعمل {acte}",
        "en": " for {acte}",
        "it": " per {acte}",
        "de": " für {acte}",
    },
    "no_rdv": {
        "fr": "Je ne vous trouve aucun rendez-vous programmé pour le moment. L'équipe peut vous en proposer un si vous le souhaitez.",
        "darija": "ما لقيتلكش موعد مبرمج توا. تنجم تتصل بالفريق باش يعملولك واحد إذا تحب.",
        "en": "I don't see any appointment scheduled for you right now. The team can arrange one if you'd like.",
        "it": "Al momento non risulta nessun appuntamento programmato. Il team può fissarne uno se lo desidera.",
        "de": "Ich finde derzeit keinen geplanten Termin für Sie. Das Team kann bei Bedarf einen vereinbaren.",
    },
    "handoff_general": {
        "fr": "Je note votre message et je le transmets à l'équipe, qui reviendra vers vous rapidement. Souhaitez-vous que je prépare autre chose ?",
        "darija": "سجلت رسالتك ونعديها للفريق، يرجعولك في أقرب وقت. تحب نعملك حاجة أخرى ؟",
        "en": "I've noted your message and I'm passing it to the team, who will get back to you shortly. Would you like me to prepare anything else?",
        "it": "Ho registrato il suo messaggio e lo trasmetto al team, che la ricontatterà a breve. Desidera che prepari qualcos'altro?",
        "de": "Ich habe Ihre Nachricht notiert und leite sie an das Team weiter, das sich bald bei Ihnen meldet. Soll ich noch etwas vorbereiten?",
    },
    "handoff_write_action": {
        "fr": "Je transmets votre demande à l'équipe pour validation (aucune modification n'est faite automatiquement). Elle vous confirmera rapidement.",
        "darija": "نعدي طلبك للفريق باش يتأكد (ما ثماش تبديل أوتوماتيكي). يأكدلك في أقرب وقت.",
        "en": "I'm passing your request to the team for validation (nothing is changed automatically). They will confirm shortly.",
        "it": "Trasmetto la sua richiesta al team per la validazione (nessuna modifica viene fatta automaticamente). Le confermeranno a breve.",
        "de": "Ich leite Ihre Anfrage zur Bestätigung an das Team weiter (nichts wird automatisch geändert). Sie erhalten in Kürze eine Rückmeldung.",
    },
    "prompt_injection_refusal": {
        "fr": "Je ne peux pas suivre cette instruction. Je reste l'assistante administrative de la clinique — comment puis-je vous aider ?",
        "darija": "ما نجمش نتبع هالطلب. نبقى مساعدة العيادة الإدارية — كيفاش نجم نعاونك ؟",
        "en": "I can't follow that instruction. I remain the clinic's administrative assistant — how can I help you?",
        "it": "Non posso seguire questa istruzione. Resto l'assistente amministrativa della clinica — come posso aiutarla?",
        "de": "Dieser Anweisung kann ich nicht folgen. Ich bleibe die administrative Assistentin der Klinik — wie kann ich Ihnen helfen?",
    },
    "rate_limited": {
        "fr": "Trop de requêtes. Veuillez patienter une minute.",
        "darija": "عندك بزاف طلبات، استنى دقيقة.",
        "en": "Too many requests. Please wait a minute.",
        "it": "Troppe richieste. Attenda un minuto.",
        "de": "Zu viele Anfragen. Bitte warten Sie eine Minute.",
    },
    "payload_too_large": {
        "fr": "Message trop long.",
        "darija": "الرسالة طويلة برشا.",
        "en": "Message too long.",
        "it": "Messaggio troppo lungo.",
        "de": "Nachricht zu lang.",
    },
}


def t(key: str, lang: str, **kwargs: str) -> str:
    """Retourne la phrase ``key`` dans ``lang`` (repli français si absent)."""
    table = _TRANSLATIONS.get(key)
    if not table:
        return ""
    text = table.get(lang) or table.get("fr") or ""
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def normalize_lang(lang: str | None) -> str:
    return lang if lang in SUPPORTED_LANGS else "fr"
