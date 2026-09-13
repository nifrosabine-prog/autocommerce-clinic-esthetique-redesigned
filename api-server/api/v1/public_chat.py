"""Chat public Lina V2.1.1 : information générale déterministe uniquement."""
from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, limiter
from config import get_settings
from services.assistant_security import MEDICAL_DISTRESS_FR, MEDICAL_DISTRESS_DARIJA, PROMPT_INJECTION_PATTERNS
from services.branding import get_public_content

logger = logging.getLogger("public_chat")
router = APIRouter(tags=["public-chat"])

class PublicChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(default=None, max_length=80)


def _public_clinic_id() -> int:
    settings = get_settings()
    if settings.env == "production" and not settings.public_routes_enabled:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat public désactivé")
    clinic_id = settings.public_clinic_id
    if not isinstance(clinic_id, int) or clinic_id <= 0:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Chat public non configuré")
    return clinic_id


def _language(text: str) -> str:
    if any("\u0600" <= char <= "\u06ff" for char in text):
        return "ar"
    lowered = text.casefold()
    if re.search(r"\b(hello|hi|hours|open|address|where|price|book|appointment)\b", lowered):
        return "en"
    return "fr"


def _contains_distress(text: str) -> bool:
    lowered = text.casefold()
    return any(term.casefold() in lowered for term in (*MEDICAL_DISTRESS_FR, *MEDICAL_DISTRESS_DARIJA))


def _contains_injection(text: str) -> bool:
    return any(pattern.search(text) for pattern in PROMPT_INJECTION_PATTERNS)


def _intent(text: str) -> str:
    lowered = text.casefold()
    if re.search(r"horaire|ouvert|samedi|dimanche|quand|وقت|مفتوح|ساعات", lowered): return "hours"
    if re.search(r"adresse|où|ou se trouve|وين|عنوان|location", lowered): return "address"
    if re.search(r"téléphone|telephone|contact|appeler|whatsapp|واتساب|phone", lowered): return "contact"
    if re.search(r"prix|tarif|combien|cost|price|botox|acide|شنوة السوم|قداش", lowered): return "price"
    if re.search(r"acte|soin|service|treatment|services|خدمات", lowered): return "acts"
    if re.search(r"rendez.?vous|rdv|موعد|réserver|reservation|حجز|book|appointment", lowered): return "booking"
    return "unknown"


def _reply(message: str, content: dict) -> tuple[str, str]:
    lang = _language(message)
    intent = _intent(message)
    branding = content.get("branding") or {}
    landing = branding.get("contenu_landing") or {}
    name = branding.get("nom_clinique") or "MBA Clinic"
    hours = landing.get("horaires") or {"fr": "sur rendez-vous", "en": "by appointment", "ar": "عن طريق موعد"}[lang]
    address = landing.get("adresse") or landing.get("ville") or {"fr": "Tunis, Tunisie", "en": "Tunis, Tunisia", "ar": "تونس، تونس"}[lang]
    phone = landing.get("telephone") or landing.get("whatsapp") or "le numéro communiqué par la clinique"
    acts = ", ".join(str(item.get("nom")) for item in (content.get("all_actes") or [])[:6] if item.get("nom"))
    if lang == "en":
        replies = {
            "hours": f"{name} welcomes patients {hours}. You can check a precise slot directly in the booking form. Would you like to book an appointment?",
            "address": f"{name} is located at {address}. The booking form is available on this page if you would like to request an appointment.",
            "contact": f"You can contact {name} at {phone}. WhatsApp is also available if you prefer to speak with the clinic.",
            "acts": f"Published services include: {acts or 'please see the services section on this page'}. I can share general information, but a practitioner must assess any personal situation.",
            "price": "Prices depend on the service and the personal assessment. The clinic can provide a tailored quotation during a consultation; I cannot recommend a treatment.",
            "booking": "You can request an appointment using the form on this page. No medical information is needed in this public chat.",
            "unknown": "I can help with opening hours, address, contact details, published services and booking. I am a virtual assistant, not a doctor.",
        }
    elif lang == "ar":
        replies = {
            "hours": f"{name} تخدم {hours}. تنجم تشوف المواعيد المتوفرة مباشرة في فورم الحجز. تحب نحيلك للحجز؟",
            "address": f"{name} موجودة في {address}. فورم الحجز موجود في الصفحة كان تحب تطلب موعد.",
            "contact": f"تنجم تتصل بـ {name} على {phone}. الواتساب موجود زادة كان تحب تحكي مع العيادة.",
            "acts": f"الخدمات المنشورة هي: {acts or 'شوف قسم الخدمات في الصفحة'}. نعطي معلومات عامة فقط، والتقييم الشخصي يعملو الطبيب.",
            "price": "السعر يختلف حسب الخدمة والتقييم الشخصي. العيادة تنجم تعطيك عرض مناسب وقت الاستشارة؛ ما نعطيش توصية طبية.",
            "booking": "تنجم تطلب موعد من الفورم الموجود في الصفحة. ما نطلبوش معلومات طبية في الشات العمومي.",
            "unknown": "نجم نعاونك في الأوقات، العنوان، الاتصال، الخدمات المنشورة والحجز. أنا مساعدة افتراضية ولست طبيبة.",
        }
    else:
        replies = {
            "hours": f"{name} reçoit {hours}. Les créneaux précis se consultent directement dans le formulaire de réservation. Souhaitez-vous que je vous y oriente ?",
            "address": f"{name} se trouve à {address}. Le formulaire de réservation est disponible sur cette page si vous souhaitez demander un rendez-vous.",
            "contact": f"Vous pouvez contacter {name} au {phone}. Le bouton WhatsApp reste disponible si vous préférez échanger avec la clinique.",
            "acts": f"Les actes publiés comprennent : {acts or 'consultez la section Nos actes de cette page'}. Je peux donner une information générale, mais un praticien doit évaluer toute situation personnelle.",
            "price": "Les tarifs dépendent de l’acte et de l’évaluation personnelle. La clinique peut établir un devis lors d’une consultation ; je ne recommande aucun traitement.",
            "booking": "Vous pouvez demander un rendez-vous avec le formulaire de cette page. Aucune information médicale n’est nécessaire dans ce chat public.",
            "unknown": "Je peux vous renseigner sur les horaires, l’adresse, les contacts, les actes publiés et la réservation. Je suis une assistante virtuelle, pas un médecin.",
        }
    return replies[intent], lang


@router.post("/chat")
@limiter.limit("10/minute")
async def public_chat_route(request: Request, payload: PublicChatRequest, db: AsyncSession = Depends(get_db)):
    clinic_id = _public_clinic_id()
    message = payload.message.strip()
    if _contains_injection(message):
        logger.warning("public_chat_injection clinic_id=%s session_id=%s", clinic_id, payload.session_id or "anonymous")
        return {"reponse": "Je ne peux pas traiter cette demande. Je peux vous aider avec les informations générales de la clinique.", "statut": "refuse", "escalade": False, "actions": []}
    if _contains_distress(message):
        logger.warning("public_chat_distress clinic_id=%s session_id=%s", clinic_id, payload.session_id or "anonymous")
        return {"reponse": "Si vous êtes en urgence vitale, appelez immédiatement les services d’urgence (15 ou 112). Ce chat ne remplace pas un professionnel ; contactez aussi la clinique dès que possible.", "statut": "urgence_medicale", "escalade": True, "actions": []}
    content = await get_public_content(db, clinic_id=clinic_id)
    response, lang = _reply(message, content)
    return {"reponse": response, "statut": "information_automatique", "escalade": False, "langue": lang, "actions": [{"type": "reservation", "label": "Réserver un rendez-vous", "href": "#reservation"}]}
