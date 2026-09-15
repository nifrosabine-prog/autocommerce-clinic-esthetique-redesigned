"""
AutoCommerce Clinic — Vérification de signature des webhooks sociaux

N'importe qui pouvait auparavant poster sur /social/messages/webhook
et injecter de faux messages (donc déclencher de fausses réponses
automatiques). Ce module vérifie une signature HMAC-SHA256 du corps
brut de la requête avant de laisser passer.

Fail-closed : si SOCIAL_WEBHOOK_SECRET n'est pas configuré, le webhook
refuse tout (503) plutôt que d'accepter des payloads non signés.
"""
import hashlib
import hmac

from fastapi import HTTPException, Request, status

from config import get_settings


def _compute_signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def verify_webhook_signature(request: Request) -> bytes:
    """Dépendance FastAPI : vérifie X-Signature (hex HMAC-SHA256 du
    corps brut) et retourne le corps pour que la route puisse le
    reparser si besoin. Comparaison en temps constant pour éviter le
    timing attack sur la signature."""
    settings = get_settings()
    if not settings.social_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook non configuré (SOCIAL_WEBHOOK_SECRET manquant)",
        )

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content-Length invalide") from exc
        if declared_length < 0 or declared_length > settings.webhook_max_body_size:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Webhook trop volumineux")

    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > settings.webhook_max_body_size:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Webhook trop volumineux")
        chunks.append(chunk)
    body = b"".join(chunks)
    request._body = body

    signature = request.headers.get("X-Signature", "")
    if not signature:
        signature = request.headers.get("X-Hub-Signature-256", "")
    if signature.startswith("sha256="):
        signature = signature[7:]
    attendu = _compute_signature(settings.social_webhook_secret, body)

    if not signature or not hmac.compare_digest(signature.lower(), attendu):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature invalide")

    return body
