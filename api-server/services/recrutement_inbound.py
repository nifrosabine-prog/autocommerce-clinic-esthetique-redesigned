"""Réception des candidatures par Resend Inbound.

Resend expose l'événement ``email.received`` via webhook. Le webhook contient
uniquement les métadonnées : le corps et les pièces jointes sont récupérés via
les endpoints Receiving API. La signature suit le format Svix (svix-id,
svix-timestamp, svix-signature). Le traitement est volontairement tolérant :
un incident de parsing, de stockage ou de base ne doit pas faire échouer la
réception du webhook et provoquer des retries en cascade.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import re
from email.utils import parseaddr
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import select

from config import get_settings
from models.database import Candidature, Poste
from services.recrutement import create_candidature
from api.v1.public_recruitment import (
    _ALLOWED_SUFFIXES,
    _ALLOWED_TYPES,
    _extract_cv_text,
)

logger = logging.getLogger(__name__)

_MAX_FILE_SIZE = 10 * 1024 * 1024
_MAX_TEXT = 12_000


def verify_resend_signature(raw_body: bytes, headers: Any, secret: str) -> bool:
    """Vérifie une signature Svix Resend sans dépendre du SDK Svix."""
    if not secret:
        return False
    msg_id = headers.get("svix-id")
    timestamp = headers.get("svix-timestamp")
    signatures = headers.get("svix-signature")
    if not msg_id or not timestamp or not signatures:
        return False
    # Refuser les timestamps manifestement anciens/futurs limite les replays.
    try:
        import time
        if abs(time.time() - int(timestamp)) > 300:
            return False
    except (TypeError, ValueError):
        return False
    key = secret.removeprefix("whsec_")
    try:
        decoded_key = base64.b64decode(key + "=" * (-len(key) % 4))
    except Exception:
        return False
    signed = f"{msg_id}.{timestamp}.".encode() + raw_body
    expected = base64.b64encode(hmac.new(decoded_key, signed, hashlib.sha256).digest()).decode()
    return any(
        hmac.compare_digest(value.removeprefix("v1,"), expected)
        for value in signatures.split(" ")
        if value.startswith("v1,")
    )


def _safe_suffix(filename: str, content_type: str) -> str | None:
    suffix = Path(filename or "").suffix.lower()
    if suffix in _ALLOWED_SUFFIXES and content_type in _ALLOWED_TYPES:
        return suffix
    return None


async def _resend_get(path: str) -> dict[str, Any]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://api.resend.com{path}",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        )
        response.raise_for_status()
        return response.json()


async def _download(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        if len(response.content) > _MAX_FILE_SIZE:
            raise ValueError("pièce jointe trop volumineuse")
        return response.content


def _clinic_id_for_email(email: dict[str, Any]) -> int | None:
    settings = get_settings()
    expected = (getattr(settings, "recruitment_inbound_email", "") or "").strip().lower()
    recipients = [str(x).lower() for x in (email.get("received_for") or email.get("to") or [])]
    if expected and expected not in recipients:
        logger.warning("E-mail entrant ignoré : destinataire inattendu")
        return None
    clinic_id = getattr(settings, "recruitment_inbound_clinic_id", None) or settings.public_clinic_id
    return clinic_id if isinstance(clinic_id, int) and clinic_id > 0 else None


def _candidate_from(sender: str) -> tuple[str, str]:
    name, address = parseaddr(sender or "")
    address = address.strip().lower()
    name = re.sub(r"\s+", " ", name or "").strip()
    return (name or address.split("@", 1)[0] or "Candidat", address)


async def process_resend_received(payload: dict[str, Any], db) -> dict[str, Any]:
    """Traite un payload email.received ; toutes les erreurs métier sont absorbées."""
    if payload.get("type") != "email.received":
        return {"status": "ignored", "reason": "event_type"}
    event = payload.get("data") or {}
    email_id = str(event.get("email_id") or "").strip()
    if not email_id:
        return {"status": "ignored", "reason": "missing_email_id"}
    try:
        email = await _resend_get(f"/emails/receiving/{email_id}")
        clinic_id = _clinic_id_for_email(email)
        if clinic_id is None:
            return {"status": "ignored", "reason": "clinic_not_resolved"}
        # Idempotence applicative : le source_email_id est ajouté par la migration.
        duplicate = await db.scalar(select(Candidature).where(
            Candidature.clinic_id == clinic_id,
            Candidature.source_email_id == email_id,
        ))
        if duplicate:
            return {"status": "duplicate", "id": duplicate.id}
        name, address = _candidate_from(email.get("from", ""))
        if "@" not in address:
            return {"status": "ignored", "reason": "sender_without_email"}
        supported = [a for a in (email.get("attachments") or []) if _safe_suffix(
            a.get("filename", ""), a.get("content_type", "")
        )]
        if not supported:
            logger.warning("E-mail entrant ignoré : aucune pièce jointe CV supportée")
            return {"status": "ignored", "reason": "no_supported_cv"}
        subject = str(email.get("subject") or "Candidature spontanée").strip()[:200]
        # Le poste est résolu par le sujet lorsque celui-ci correspond à un poste ouvert.
        poste = await db.scalar(select(Poste).where(
            Poste.clinic_id == clinic_id,
            Poste.statut == "ouvert",
            Poste.titre.ilike(f"%{subject}%"),
        ))
        candidature = await create_candidature({
            "poste_id": poste.id if poste else None,
            "poste": poste.titre if poste else subject or "Candidature spontanée",
            "nom_candidat": name[:200],
            "email": address[:255],
        }, db, clinic_id=clinic_id, created_by_id=None)
        candidature.source_email_id = email_id
        for attachment in supported:
            suffix = _safe_suffix(attachment.get("filename", ""), attachment.get("content_type", ""))
            if suffix is None:
                logger.warning("Pièce jointe CV ignorée : format non supporté")
                continue
            details = await _resend_get(
                f"/emails/receiving/{email_id}/attachments/{attachment.get('id')}"
            )
            content = await _download(details["download_url"])
            if not content or len(content) > _MAX_FILE_SIZE:
                continue
            settings = get_settings()
            folder = Path(settings.uploads_dir) / "recrutement" / str(clinic_id) / str(candidature.id)
            folder.mkdir(parents=True, exist_ok=True)
            filename = f"{uuid4().hex}{suffix}"
            (folder / filename).write_bytes(content)
            candidature.cv_url = f"/api/v1/recrutement/{candidature.id}/documents/{filename}"
            candidature.cv_texte_extrait = _extract_cv_text(content, suffix)[:_MAX_TEXT] or None
            break
        await db.flush()
        return {"status": "created", "id": candidature.id}
    except Exception:
        logger.exception("Traitement candidature inbound échoué (email_id=%s)", email_id)
        return {"status": "ignored", "reason": "processing_error"}
