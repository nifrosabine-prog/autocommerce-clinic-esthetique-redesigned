"""Service central WhatsApp Business API avec politique fail-closed."""

import logging
from typing import Optional

import httpx

from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _preflight(kind: str) -> Optional[dict]:
    """Retourne une réponse locale si l’envoi externe est interdit."""
    if not settings.wa_business_token or not settings.wa_phone_id:
        logger.warning("[WA DEV] WhatsApp non configuré — %s non envoyé", kind)
        return {
            "status": "dev_mode",
            "warning": "WhatsApp non configuré — message non envoyé",
        }
    if not settings.whatsapp_enabled:
        logger.warning("WhatsApp désactivé — %s non envoyé", kind)
        return {"status": "disabled", "warning": "WhatsApp désactivé"}
    if "whatsapp" not in settings.allowed_external_integrations:
        logger.warning("WhatsApp absent de l'allowlist — %s non envoyé", kind)
        return {"status": "blocked", "warning": "WhatsApp absent de l'allowlist"}
    return None


def _endpoint() -> str:
    return f"{settings.wa_base_url}/{settings.wa_api_version}/{settings.wa_phone_id}/messages"


async def send_whatsapp_message(to_phone: str, message: str) -> dict:
    """Envoie un message WhatsApp uniquement si la politique serveur l’autorise."""
    blocked = _preflight("message")
    if blocked:
        blocked["message"] = message if blocked["status"] == "dev_mode" else ""
        return blocked

    headers = {
        "Authorization": f"Bearer {settings.wa_business_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"body": message[:4096]},
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(_endpoint(), headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


async def send_whatsapp_template(
    to_phone: str,
    template_name: str,
    language: str = "fr",
    components: list | None = None,
) -> dict:
    """Envoie un template WhatsApp uniquement si la politique serveur l’autorise."""
    blocked = _preflight(f"template {template_name}")
    if blocked:
        blocked["template"] = template_name
        return blocked

    headers = {
        "Authorization": f"Bearer {settings.wa_business_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
        },
    }
    if components:
        payload["template"]["components"] = components

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(_endpoint(), headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
