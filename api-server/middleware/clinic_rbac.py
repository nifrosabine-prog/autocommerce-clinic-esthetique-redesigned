"""
AutoCommerce Clinic — Matrice RBAC stricte (Bloc 2 — rôles et permissions)

V2 corrigée (2026-09-09) : alignement avec le Bloc 2 du cahier des charges.

Principes appliqués :
  1. Un rôle technique (admin) n'obtient PAS automatiquement l'accès aux
     données médicales : dossiers en lecture technique auditée, photos et
     notes privées refusées par défaut.
  2. Le médecin peut AFFICHER les prix (bouton) mais ne peut pas les
     modifier. Il n'a aucune permission financière (pas de remise, pas de
     validation de devis, pas de paiement, pas de conversion).
  3. L'assistante gère la validation financière et le paiement selon ses
     droits ; elle n'a pas accès aux dossiers médicaux ni aux photos.
  4. L'esthéticienne et le prestataire (masseuse, etc.) ne voient que les
     données nécessaires à leur intervention ; les prix restent masqués.
  5. Chaque permission de la liste Bloc 2 est vérifiable côté backend via
     require_permission(resource, action). Les contrôles frontend ne sont
     qu'une aide d'interface.

Rôles couverts : DIRECTRICE, MEDECIN, ESTHETICIENNE, ASSISTANTE, COMMERCIAL,
ADMIN (technique), SUPER_ADMIN (plateforme), PRESTATAIRE (masseuse...).
"""

from typing import Any, Iterable, Optional

from fastapi import Depends, HTTPException, status

from middleware.auth import get_current_active_user
from models.database import RoleEnum, Utilisateur


# ── Matrice des permissions (resources × rôles) ─────────────

RESOURCE_PERMISSIONS = {
    # ── Données administratives / relationnelles ──────────────
    "patients": {
        RoleEnum.DIRECTRICE: ["read", "write", "delete"],
        RoleEnum.MEDECIN: ["read", "write"],
        RoleEnum.ESTHETICIENNE: ["read", "write"],
        RoleEnum.ASSISTANTE: ["read", "write"],
        RoleEnum.COMMERCIAL: ["read"],          # Ses patientes uniquement
        RoleEnum.ADMIN: ["read", "write", "delete"],  # Technique, pas médical
        RoleEnum.SUPER_ADMIN: ["read", "write", "delete"],
        RoleEnum.PRESTATAIRE: ["read"],         # Contexte de son intervention
    },
    "agenda": {
        RoleEnum.DIRECTRICE: ["read", "write", "delete"],
        RoleEnum.MEDECIN: ["read", "write"],
        RoleEnum.ESTHETICIENNE: ["read", "write"],
        RoleEnum.ASSISTANTE: ["read", "write", "delete"],
        RoleEnum.COMMERCIAL: ["read"],
        RoleEnum.ADMIN: ["read", "write", "delete"],
        RoleEnum.SUPER_ADMIN: ["read", "write", "delete"],
        RoleEnum.PRESTATAIRE: ["read", "write"],  # Ses interventions
    },
    "factures": {
        RoleEnum.DIRECTRICE: ["read", "write", "delete"],
        RoleEnum.MEDECIN: ["read"],
        RoleEnum.ESTHETICIENNE: ["read"],
        RoleEnum.ASSISTANTE: ["read", "write"],
        RoleEnum.COMMERCIAL: ["read"],          # Ses patientes
        RoleEnum.ADMIN: ["read", "write", "delete"],
        RoleEnum.SUPER_ADMIN: ["read", "write", "delete"],
        RoleEnum.PRESTATAIRE: [],
    },
    "commissions": {
        RoleEnum.DIRECTRICE: ["read", "write", "validate"],
        RoleEnum.MEDECIN: [],
        RoleEnum.ESTHETICIENNE: [],
        RoleEnum.ASSISTANTE: [],
        RoleEnum.COMMERCIAL: ["read"],          # Ses commissions
        RoleEnum.ADMIN: ["read", "write", "delete"],
        RoleEnum.SUPER_ADMIN: ["read", "write", "delete"],
        RoleEnum.PRESTATAIRE: [],
    },
    "depenses": {
        RoleEnum.DIRECTRICE: ["read", "write", "delete", "validate"],
        RoleEnum.MEDECIN: [],
        RoleEnum.ESTHETICIENNE: [],
        RoleEnum.ASSISTANTE: ["read", "write"],
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["read", "write", "delete"],
        RoleEnum.SUPER_ADMIN: ["read", "write", "delete"],
        RoleEnum.PRESTATAIRE: [],
    },
    "recrutement": {
        RoleEnum.DIRECTRICE: ["read", "write", "delete"],
        RoleEnum.MEDECIN: ["read"],
        RoleEnum.ESTHETICIENNE: [],
        RoleEnum.ASSISTANTE: ["read", "write"],
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["read", "write", "delete"],
        RoleEnum.SUPER_ADMIN: ["read", "write", "delete"],
        RoleEnum.PRESTATAIRE: [],
    },
    "marketing": {
        RoleEnum.DIRECTRICE: ["read", "write", "delete"],
        RoleEnum.MEDECIN: [],
        RoleEnum.ESTHETICIENNE: [],
        RoleEnum.ASSISTANTE: ["read", "write"],
        RoleEnum.COMMERCIAL: ["read", "write"],
        RoleEnum.ADMIN: ["read", "write", "delete"],
        RoleEnum.SUPER_ADMIN: ["read", "write", "delete"],
        RoleEnum.PRESTATAIRE: [],
    },
    "settings": {
        RoleEnum.DIRECTRICE: ["read", "write"],
        RoleEnum.ADMIN: ["read", "write", "delete"],
        RoleEnum.SUPER_ADMIN: ["read", "write", "delete"],
    },

    # ── Données médicales / cliniques ─────────────────────────
    # Bloc 2 : l'admin technique n'a PAS l'accès automatique aux données
    # médicales. Lecture technique possible sur les dossiers (auditée),
    # jamais en écriture ; photos et notes privées refusées par défaut.
    "dossiers_medicaux": {
        RoleEnum.DIRECTRICE: ["read"],   # Lecture administrative, sans écriture
        RoleEnum.MEDECIN: ["read", "write"],
        RoleEnum.ESTHETICIENNE: ["read", "write"],  # Pas antécédents (filtrage champs)
        RoleEnum.ASSISTANTE: [],          # PAS accès
        RoleEnum.COMMERCIAL: [],          # PAS accès
        RoleEnum.ADMIN: ["read"],         # Accès technique AUDITÉ, jamais écriture
        RoleEnum.SUPER_ADMIN: ["read"],   # Plateforme : lecture auditée
        RoleEnum.PRESTATAIRE: [],          # Pas d'accès direct : voir notes_partagees
    },
    "photos": {
        RoleEnum.DIRECTRICE: [],          # PAS accès photos médicales
        RoleEnum.MEDECIN: ["read", "write", "delete"],
        RoleEnum.ESTHETICIENNE: ["read", "write"],
        RoleEnum.ASSISTANTE: [],          # PAS accès
        RoleEnum.COMMERCIAL: [],          # PAS accès
        RoleEnum.ADMIN: [],               # PAS d'accès automatique (Bloc 2)
        RoleEnum.SUPER_ADMIN: ["read"],   # Lecture technique auditée
        RoleEnum.PRESTATAIRE: [],
    },
    "notes_privees": {
        RoleEnum.DIRECTRICE: ["read"],
        RoleEnum.MEDECIN: ["read", "write"],
        RoleEnum.ESTHETICIENNE: ["read", "write"],   # Ses notes uniquement
        RoleEnum.ASSISTANTE: [],          # PAS accès
        RoleEnum.COMMERCIAL: [],          # PAS accès
        RoleEnum.ADMIN: [],               # PAS d'accès automatique (Bloc 2)
        RoleEnum.SUPER_ADMIN: ["read"],
        RoleEnum.PRESTATAIRE: ["read", "write"],     # Ses notes uniquement
    },
    "notes_partagees": {
        RoleEnum.DIRECTRICE: ["read", "write"],
        RoleEnum.MEDECIN: ["read", "write"],
        RoleEnum.ESTHETICIENNE: ["read", "write"],
        RoleEnum.ASSISTANTE: ["read"],
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["read"],
        RoleEnum.SUPER_ADMIN: ["read", "write"],
        RoleEnum.PRESTATAIRE: ["read", "write"],
    },
    "interventions": {
        RoleEnum.DIRECTRICE: ["read", "validate"],            # Correction exceptionnelle, pas de création
        RoleEnum.MEDECIN: ["read", "create", "start", "validate"],
        RoleEnum.ESTHETICIENNE: ["read", "create", "start", "validate"],  # Les siennes
        RoleEnum.ASSISTANTE: ["read"],
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["read"],         # Technique, sans pilotage clinique
        RoleEnum.SUPER_ADMIN: ["read"],
        RoleEnum.PRESTATAIRE: ["read", "create", "start", "validate"],    # Les siennes
    },
    "episodes": {
        RoleEnum.DIRECTRICE: ["read", "cloturer"],
        RoleEnum.MEDECIN: ["read", "cloturer"],
        RoleEnum.ESTHETICIENNE: ["read"],
        RoleEnum.ASSISTANTE: ["read"],
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["read"],
        RoleEnum.SUPER_ADMIN: ["read"],
        RoleEnum.PRESTATAIRE: ["read"],
    },
    "actes": {
        RoleEnum.DIRECTRICE: ["read", "write"],
        RoleEnum.MEDECIN: ["read", "proposer"],
        RoleEnum.ESTHETICIENNE: ["read", "proposer"],   # Actes esthétiques autorisés
        RoleEnum.ASSISTANTE: ["read"],
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["read", "write"],
        RoleEnum.SUPER_ADMIN: ["read", "write"],
        RoleEnum.PRESTATAIRE: ["read", "proposer"],     # Prestations autorisées
    },

    # ── Finances ──────────────────────────────────────────────
    "prix": {
        RoleEnum.DIRECTRICE: ["read", "write"],
        RoleEnum.MEDECIN: ["read"],       # AFFICHAGE uniquement (Bloc 2)
        RoleEnum.ESTHETICIENNE: [],       # Masqué par défaut
        RoleEnum.ASSISTANTE: ["read", "write"],
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["read", "write"],
        RoleEnum.SUPER_ADMIN: ["read", "write"],
        RoleEnum.PRESTATAIRE: [],         # Masqué par défaut
    },
    "remise": {
        RoleEnum.DIRECTRICE: ["apply"],
        RoleEnum.MEDECIN: [],
        RoleEnum.ESTHETICIENNE: [],
        RoleEnum.ASSISTANTE: ["apply"],   # Selon ses droits
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["apply"],
        RoleEnum.SUPER_ADMIN: ["apply"],
        RoleEnum.PRESTATAIRE: [],
    },
    "devis": {
        RoleEnum.DIRECTRICE: ["read", "write", "validate", "convertir"],
        RoleEnum.MEDECIN: ["read"],       # Voit les actes, PAS les prix par défaut
        RoleEnum.ESTHETICIENNE: ["read"],
        RoleEnum.ASSISTANTE: ["read", "write", "validate", "convertir"],
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["read", "write"],
        RoleEnum.SUPER_ADMIN: ["read", "write", "validate", "convertir"],
        RoleEnum.PRESTATAIRE: [],
    },
    "paiements": {
        RoleEnum.DIRECTRICE: ["read", "enregistrer"],
        RoleEnum.MEDECIN: [],
        RoleEnum.ESTHETICIENNE: [],
        RoleEnum.ASSISTANTE: ["read", "enregistrer"],
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["read", "enregistrer"],
        RoleEnum.SUPER_ADMIN: ["read", "enregistrer"],
        RoleEnum.PRESTATAIRE: [],
    },

    # ── Stock & outils cliniques ──────────────────────────────
    "stock_injectables": {
        RoleEnum.DIRECTRICE: ["read", "write", "delete"],
        RoleEnum.MEDECIN: ["read"],
        RoleEnum.ESTHETICIENNE: ["read"],
        RoleEnum.ASSISTANTE: ["read", "write", "delete"],
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["read", "write", "delete"],
        RoleEnum.SUPER_ADMIN: ["read", "write", "delete"],
        RoleEnum.PRESTATAIRE: ["read"],
    },
    "stock_consommables": {
        RoleEnum.DIRECTRICE: ["read", "write", "delete"],
        RoleEnum.MEDECIN: ["read"],
        RoleEnum.ESTHETICIENNE: ["read"],
        RoleEnum.ASSISTANTE: ["read", "write", "delete"],
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["read", "write", "delete"],
        RoleEnum.SUPER_ADMIN: ["read", "write", "delete"],
        RoleEnum.PRESTATAIRE: ["read"],
    },
    "lots": {
        RoleEnum.DIRECTRICE: ["read", "utiliser"],
        RoleEnum.MEDECIN: ["read", "utiliser"],
        RoleEnum.ESTHETICIENNE: ["read", "utiliser"],
        RoleEnum.ASSISTANTE: ["read"],
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["read", "utiliser"],
        RoleEnum.SUPER_ADMIN: ["read", "utiliser"],
        RoleEnum.PRESTATAIRE: ["read", "utiliser"],
    },
    "simulation_ia": {
        RoleEnum.DIRECTRICE: ["read", "run"],
        RoleEnum.MEDECIN: ["read", "run"],
        RoleEnum.ESTHETICIENNE: ["read"],
        RoleEnum.ASSISTANTE: [],
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["read", "run"],
        RoleEnum.SUPER_ADMIN: ["read", "run"],
        RoleEnum.PRESTATAIRE: [],
    },
}

# ── Mapping des permissions métier Bloc 2 ────────────────────
# Chaque action nommée du cahier des charges pointe vers (resource, action)
# de la matrice. C'est la liste unique de vérification backend.

BLOC2_ACTIONS = {
    "admin_data":              ("patients", "read"),
    "read_medical":            ("dossiers_medicaux", "read"),
    "write_medical":           ("dossiers_medicaux", "write"),
    "access_private_notes":    ("notes_privees", "read"),
    "create_private_note":     ("notes_privees", "write"),
    "create_shared_note":      ("notes_partagees", "write"),
    "create_intervention":     ("interventions", "create"),
    "start_intervention":      ("interventions", "start"),
    "validate_intervention":   ("interventions", "validate"),
    "manage_actes":            ("actes", "write"),
    "propose_actes":           ("actes", "proposer"),
    "view_price":              ("prix", "read"),
    "edit_price":              ("prix", "write"),
    "apply_remise":            ("remise", "apply"),
    "validate_financial":      ("devis", "validate"),
    "convert_devis":           ("devis", "convertir"),
    "register_payment":        ("paiements", "enregistrer"),
    "access_photos":           ("photos", "read"),
    "run_simulation_ia":       ("simulation_ia", "run"),
    "use_lot":                 ("lots", "utiliser"),
    "close_episode":           ("episodes", "cloturer"),
}


# ── Helpers génériques ───────────────────────────────────────

def _extract_user_role(current_user: Any) -> str | None:
    """Accepte le contrat principal de l'app (dict) ET les objets ORM/mock des tests."""
    if isinstance(current_user, dict):
        return current_user.get("role")
    return getattr(current_user, "role", None)


def _to_role_enum(role_value: str) -> Optional[RoleEnum]:
    if isinstance(role_value, RoleEnum):
        return role_value
    for r in RoleEnum:
        if r.value == role_value:
            return r
    return None


def _normalize_allowed_roles(allowed_roles: tuple[Any, ...]) -> list[RoleEnum]:
    """Accepte require_role(RoleEnum.A, RoleEnum.B) ET
    require_role([RoleEnum.A, RoleEnum.B])."""
    normalized: list[RoleEnum] = []

    for role in allowed_roles:
        if isinstance(role, RoleEnum):
            normalized.append(role)
            continue

        if isinstance(role, Iterable) and not isinstance(role, (str, bytes)):
            for item in role:
                if not isinstance(item, RoleEnum):
                    raise TypeError(f"Rôle invalide: {item!r}")
                normalized.append(item)
            continue

        raise TypeError(f"Rôle invalide: {role!r}")

    return normalized


def _role_has_permission(role_enum: RoleEnum, resource: str, action: str) -> bool:
    """Vérification pure matrice : role_enum a-t-il (resource, action) ?"""
    if resource not in RESOURCE_PERMISSIONS:
        return False
    permissions = RESOURCE_PERMISSIONS[resource].get(role_enum, [])
    return action in permissions


def check_permission(user_role: str, resource: str, action: str) -> bool:
    """Vérifie si un rôle a la permission sur une ressource.

    Args:
        user_role: Valeur du rôle (ex: "medecin")
        resource: Nom de la ressource (ex: "dossiers_medicaux")
        action: Action demandée (ex: "read", "write")

    Returns:
        True si autorisé, False sinon
    """
    role_enum = _to_role_enum(user_role)
    if role_enum is None:
        return False
    return _role_has_permission(role_enum, resource, action)


def check_bloc2_action(user_role: str, action_name: str) -> bool:
    """Vérifie une action nommée du Bloc 2 (voir BLOC2_ACTIONS)."""
    mapped = BLOC2_ACTIONS.get(action_name)
    if mapped is None:
        return False
    return check_permission(user_role, mapped[0], mapped[1])


def get_role_permissions(user_role: str) -> dict[str, list[str]]:
    """Retourne l'agrégat des permissions du rôle sur toutes les ressources."""
    role_enum = _to_role_enum(user_role)
    if role_enum is None:
        return {}
    return {
        resource: list(perms)
        for resource, perms in RESOURCE_PERMISSIONS.items()
        if perms.get(role_enum)
    }


def get_bloc2_permissions(user_role: str) -> list[str]:
    """Liste des actions Bloc 2 autorisées pour un rôle."""
    return [
        name for name, (resource, action) in BLOC2_ACTIONS.items()
        if check_permission(user_role, resource, action)
    ]


def can_view_prices(user_role: str) -> bool:
    """Le médecin peut AFFICHER les prix (bouton) ; jamais les modifier."""
    return check_permission(user_role, "prix", "read")


def can_edit_prices(user_role: str) -> bool:
    """Qui peut modifier les prix : jamais le médecin."""
    return check_permission(user_role, "prix", "write")


def can_access_private_notes(user_role: str) -> bool:
    """Notes privées : jamais l'assistante, le commercial ni l'admin."""
    return check_permission(user_role, "notes_privees", "read")


# ── require_role (compatibilité historique) ──────────────────

def require_role(*allowed_roles: RoleEnum):
    """Décorateur FastAPI Depends vérifiant le rôle de l'utilisateur.

    Usage:
        @router.get("/patients")
        async def list_patients(
            current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.DIRECTRICE)),
        ):
            ...
    """
    normalized_roles = _normalize_allowed_roles(allowed_roles)
    allowed_values = [r.value for r in normalized_roles]

    async def role_checker(current_user: dict | Utilisateur = Depends(get_current_active_user)) -> dict | Utilisateur:
        user_role = _extract_user_role(current_user)

        if not user_role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Rôle utilisateur non défini",
            )

        if user_role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé. Rôles autorisés : {allowed_values}",
            )

        return current_user

    return role_checker


# ── require_permission (Bloc 2) ──────────────────────────────

def require_permission(resource: str, action: str, allowed_roles: tuple[RoleEnum, ...] = ()):
    """Décorateur FastAPI Depends — vérification backend de (resource, action).

    La permission est déterminée par la matrice RESPOURCE_PERMISSIONS.
    `allowed_roles` est un garde-fou optionnel pour les routes qui doivent
    rester accessibles à un rôle non couvert par la matrice (rétrocompat).

    Toute action interdite renvoie une erreur backend explicite (403) avec
    le nom de la resource et de l'action refusées — jamais le détail des
    données.

    Usage:
        @router.post("/factures/{facture_id}/payer")
        async def payer(
            current_user=Depends(require_permission("paiements", "enregistrer")),
        ):
            ...
    """
    explicit_roles = _normalize_allowed_roles(allowed_roles)
    explicit_values = [r.value for r in explicit_roles]

    async def permission_checker(
        current_user: dict | Utilisateur = Depends(get_current_active_user),
    ) -> dict | Utilisateur:
        user_role = _extract_user_role(current_user)
        if not user_role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Rôle utilisateur non défini",
            )

        allowed = _role_has_permission(_to_role_enum(user_role), resource, action)
        if not allowed and explicit_values:
            allowed = user_role in explicit_values

        if not allowed:
            raise PermissionDenied(
                detail=f"Permission refusée : action '{action}' sur la ressource '{resource}'"
            )

        return current_user

    return permission_checker


class PermissionDenied(HTTPException):
    def __init__(self, detail: str = "Permission refusée"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
