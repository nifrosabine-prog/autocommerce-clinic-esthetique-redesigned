"""
AutoCommerce Clinic — Branding / configuration de la landing page

Une instance = un client, donc pas de multi-tenant : c'est un unique
enregistrement de configuration (clé "branding" dans ClinicSetting),
lu publiquement par la landing page et modifiable par la direction.
"""
import os
import uuid

from PIL import Image as PILImage
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from services.clinic_settings import get_setting, set_setting
from core.llm_client import get_llm_client
from models.database import ActeMedical
from sqlalchemy import select

settings = get_settings()

BRANDING_KEY = "branding"
PUBLIC_DEMO_MARKERS = ("demo", "synthetic", "railway", "audit validation", "test environment")

DEFAULT_BRANDING = {
    "nom_clinique": "AutoCommerce Clinic",
    "logo_url": None,
    "couleur_primaire": "#0EA5A4",
    "couleur_secondaire": "#0F172A",
    "contenu_landing": {
        "titre": "Bienvenue",
        "sous_titre": "",
        "services_mis_en_avant": [],
        "adresse": "",
        "ville": "",
        "telephone": "",
        "whatsapp": "",
        "email": "",
        "instagram": "",
        "facebook": "",
        "tiktok": "",
        "photo_hero_url": None,
        "description_longue": "",
        "horaires": "",
    },
}

LOGO_ALLOWED_MIMETYPES = {"image/jpeg", "image/png", "image/webp"}
MIME_TO_PIL_FORMAT = {"image/jpeg": "jpeg", "image/png": "png", "image/webp": "webp"}
MIME_TO_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_LOGO_SIZE_MB = 2


async def get_branding(db: AsyncSession, clinic_id: int | None = None) -> dict:
    stored = await get_setting(BRANDING_KEY, db, default=None, clinic_id=clinic_id)
    if not stored:
        return DEFAULT_BRANDING
    # merge superficiel : les clés absentes du stockage retombent sur le défaut
    merged = {**DEFAULT_BRANDING, **stored}
    merged["contenu_landing"] = {**DEFAULT_BRANDING["contenu_landing"], **stored.get("contenu_landing", {})}
    return merged


def sanitize_public_branding(branding: dict) -> dict:
    """Ne jamais publier une adresse ou coordonnée explicitement synthétique."""
    public = {**branding, "contenu_landing": {**(branding.get("contenu_landing") or {})}}
    landing = public["contenu_landing"]
    for key in ("adresse", "ville", "telephone", "whatsapp", "email"):
        value = str(landing.get(key) or "")
        if any(marker in value.lower() for marker in PUBLIC_DEMO_MARKERS):
            landing[key] = ""
    return public


async def get_branding_context(db: AsyncSession, clinic_id: int | None = None) -> dict:
    """Retourne les valeurs branding déjà normalisées pour les services.

    Clés stables :
    - clinic_name
    - primary_color
    - secondary_color
    - address
    - phone
    - logo_url
    """
    branding = await get_branding(db, clinic_id=clinic_id)
    landing = branding.get("contenu_landing") or {}
    return {
        "clinic_name": branding.get("nom_clinique") or DEFAULT_BRANDING["nom_clinique"],
        "primary_color": branding.get("couleur_primaire") or DEFAULT_BRANDING["couleur_primaire"],
        "secondary_color": branding.get("couleur_secondaire") or DEFAULT_BRANDING["couleur_secondaire"],
        "address": landing.get("adresse") or "",
        "phone": landing.get("telephone") or "",
        "logo_url": branding.get("logo_url"),
    }


async def update_branding(data: dict, db: AsyncSession, clinic_id: int | None = None) -> dict:
    current = await get_branding(db, clinic_id=clinic_id)
    for key in ("nom_clinique", "logo_url", "couleur_primaire", "couleur_secondaire"):
        if key in data and data[key] is not None:
            current[key] = data[key]
    if "contenu_landing" in data and data["contenu_landing"]:
        current["contenu_landing"] = {**current["contenu_landing"], **data["contenu_landing"]}

    await set_setting(
        BRANDING_KEY,
        current,
        db,
        description="Branding et contenu de la landing page",
        clinic_id=clinic_id,
    )
    return current


async def generate_marketing_summary(db: AsyncSession, clinic_id: int, acts: list[ActeMedical]) -> str:
    """Génère un texte de présentation attractif basé sur les actes disponibles."""
    if not acts:
        return "Découvrez nos soins esthétiques personnalisés pour sublimer votre beauté naturelle."

    act_names = [a.nom for a in acts]
    categories = list(set(a.categorie for a in acts))
    
    prompt = f"""
    Tu es un expert en marketing pour cliniques esthétiques de luxe.
    Génère un paragraphe d'introduction (3-4 phrases) pour une landing page.
    La clinique propose les services suivants : {', '.join(act_names)}.
    Les domaines d'expertise sont : {', '.join(categories)}.
    Le ton doit être professionnel, rassurant et élégant.
    Langue : Français.
    Ne mentionne pas de prix.
    """
    
    llm = get_llm_client(settings)
    messages = [{"role": "user", "content": prompt}]
    
    response = await llm.chat(
        messages,
        max_tokens=300,
        temperature=0.7,
        budget_subject=f"clinic:{clinic_id}:marketing",
        budget_clinic_id=clinic_id
    )
    
    if hasattr(response, "text"):
        return response.text
    return f"Votre destination d'excellence pour la {', '.join(categories[:2])} et bien plus encore."


async def get_public_content(db: AsyncSession, clinic_id: int) -> dict:
    """Consolide tout le contenu nécessaire à la landing page dynamique."""
    branding = sanitize_public_branding(await get_branding(db, clinic_id=clinic_id))
    
    # Récupérer les actes actifs
    res_actes = await db.execute(
        select(ActeMedical)
        .where(ActeMedical.clinic_id == clinic_id)
        .where(ActeMedical.is_active)
        .where(ActeMedical.is_public)
        .order_by(ActeMedical.categorie, ActeMedical.nom)
    )
    actes = res_actes.scalars().all()
    
    # Grouper par catégorie
    grouped_actes = {}
    for acte in actes:
        if acte.categorie not in grouped_actes:
            grouped_actes[acte.categorie] = []
        grouped_actes[acte.categorie].append({
            "id": acte.id,
            "nom": acte.nom,
            "description": acte.description,
            "prix_base": float(acte.prix_base) if acte.prix_base else 0,
        })
    
    # Devise
    currency = await get_setting("clinic.currency", db, clinic_id=clinic_id)
    if not currency:
        currency = {"currency_code": "TND", "currency_symbol": "DT"}
        
    # La landing publique ne doit pas dépendre d’un appel LLM synchrone.
    # Le texte configuré par la direction est la source de vérité ; le fallback
    # statique garantit une réponse disponible même si le fournisseur IA est lent
    # ou temporairement indisponible.
    landing_content = branding.get("contenu_landing") or {}
    marketing_summary = landing_content.get("sous_titre") or (
        "Découvrez nos soins esthétiques personnalisés dans un cadre médical sécurisé."
        if actes else "Découvrez nos soins esthétiques personnalisés."
    )
    
    return {
        "branding": branding,
        "expertises": grouped_actes,
        "currency": currency,
        "marketing_summary": marketing_summary,
        "all_actes": [
            {"id": a.id, "nom": a.nom, "categorie": a.categorie, "duree_minutes": a.duree_minutes}
            for a in actes
        ]
    }


def save_logo(file_bytes: bytes, mime_type: str, clinic_id: int | None = None) -> str:
    """Valide (taille + contenu réel via magic-bytes) puis enregistre le
    logo sur disque. Retourne l'URL relative à exposer publiquement.
    Pas de chiffrement : un logo n'est pas une donnée sensible."""
    if mime_type not in LOGO_ALLOWED_MIMETYPES:
        raise ValueError(f"Type MIME non autorisé : {mime_type}. Autorisés : {LOGO_ALLOWED_MIMETYPES}")

    if len(file_bytes) > MAX_LOGO_SIZE_MB * 1024 * 1024:
        raise ValueError(f"Logo trop volumineux (max {MAX_LOGO_SIZE_MB} Mo)")

    try:
        import io
        probe = PILImage.open(io.BytesIO(file_bytes))
        probe.verify()
    except Exception:
        raise ValueError("Le fichier n'est pas une image valide")

    detected_format = (probe.format or "").lower()
    if MIME_TO_PIL_FORMAT.get(mime_type) != detected_format:
        raise ValueError(
            f"Le contenu du fichier ({detected_format or 'inconnu'}) ne correspond pas "
            f"au type déclaré ({mime_type})"
        )

    if clinic_id is not None and int(clinic_id) <= 0:
        raise ValueError("clinic_id invalide")
    branding_dir = settings.branding_dir
    relative_dir = ""
    if clinic_id is not None:
        relative_dir = f"clinic-{int(clinic_id)}"
        branding_dir = branding_dir / relative_dir
    os.makedirs(str(branding_dir), exist_ok=True)
    filename = f"logo-{uuid.uuid4().hex[:12]}.{MIME_TO_EXT[mime_type]}"
    filepath = os.path.join(str(branding_dir), filename)
    with open(filepath, "wb") as f:
        f.write(file_bytes)

    return f"/static/branding/{relative_dir + '/' if relative_dir else ''}{filename}"


def save_hero(file_bytes: bytes, mime_type: str, clinic_id: int | None = None) -> str:
    """Valide et enregistre la photo hero publique de la clinique."""
    if mime_type not in LOGO_ALLOWED_MIMETYPES:
        raise ValueError(f"Type MIME non autorisé : {mime_type}. Autorisés : {LOGO_ALLOWED_MIMETYPES}")
    if len(file_bytes) > MAX_LOGO_SIZE_MB * 1024 * 1024:
        raise ValueError(f"Photo trop volumineuse (max {MAX_LOGO_SIZE_MB} Mo)")
    import io
    try:
        probe = PILImage.open(io.BytesIO(file_bytes))
        detected_format = (probe.format or "").lower()
        probe.verify()
    except Exception as exc:
        raise ValueError("Le fichier n'est pas une image valide") from exc
    if MIME_TO_PIL_FORMAT.get(mime_type) != detected_format:
        raise ValueError("Le contenu du fichier ne correspond pas au type déclaré")
    if clinic_id is not None and int(clinic_id) <= 0:
        raise ValueError("clinic_id invalide")
    branding_dir = settings.branding_dir
    relative_dir = ""
    if clinic_id is not None:
        relative_dir = f"clinic-{int(clinic_id)}"
        branding_dir = branding_dir / relative_dir
    os.makedirs(str(branding_dir), exist_ok=True)
    filename = f"hero-{uuid.uuid4().hex[:12]}.{MIME_TO_EXT[mime_type]}"
    filepath = os.path.join(str(branding_dir), filename)
    with open(filepath, "wb") as f:
        f.write(file_bytes)
    return f"/static/branding/{relative_dir + '/' if relative_dir else ''}{filename}"
