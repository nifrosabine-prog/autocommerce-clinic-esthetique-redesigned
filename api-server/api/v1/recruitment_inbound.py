"""Webhook public Resend Inbound pour les candidatures.

Resend Receiving est retenu plutôt qu'un polling IMAP : il fournit un événement
``email.received`` en temps réel, puis une API officielle pour récupérer le
message et chaque pièce jointe. Le corps du webhook ne contient pas les fichiers.
"""
import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from config import get_settings
from services.recrutement_inbound import process_resend_received, verify_resend_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recrutement", tags=["public-recruitment-inbound"])


@router.post("/inbound/resend")
async def resend_received_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    raw_body = await request.body()
    if not settings.webhooks_enabled:
        return JSONResponse({"status": "ignored", "reason": "webhooks_disabled"}, status_code=200)
    if not settings.resend_webhook_signing_secret:
        logger.error("Resend inbound refusé : RESEND_WEBHOOK_SIGNING_SECRET absent")
        return JSONResponse({"status": "misconfigured"}, status_code=503)
    if not verify_resend_signature(raw_body, request.headers, settings.resend_webhook_signing_secret):
        return JSONResponse({"status": "invalid_signature"}, status_code=401)
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return JSONResponse({"status": "invalid_json"}, status_code=200)
    result = await process_resend_received(payload, db)
    # Les erreurs métier sont loggées et absorbées pour éviter les retries infinis.
    return JSONResponse(result, status_code=200)
