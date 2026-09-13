"""
AutoCommerce Clinic — Service RBAC (Bloc 2)

Règles d'accès métier qui dépassent la simple matrice statique :
  - portée clinique (clinic_id) obligatoire ;
  - portée d'intervention : un professionnel de soin ne démarre/valide que
    SES interventions (médecin, esthéticienne, prestataire) ;
  - notes privées : l'auteur voit les siennes ; le médecin et la direction
    voient l'ensemble ; admin technique jamais ;
  - politique d'affichage des prix (médecin : afficher sans modifier) ;
  - résumé des permissions d'un rôle pour l'interface (/rbac/me).

Toutes les fonctions lèvent HTTPException(403) avec un message explicite
(critère d'acceptation Bloc 2 : erreur backend explicite).
"""

from typing import Any, Optional

from fastapi import HTTPException, status

from middleware.clinic_rbac import (
    can_access_private_notes,
    can_edit_prices,
    can_view_prices,
    get_bloc2_permissions,
    get_role_permissions,
    check_permission,
)


PROFESSIONNELS_DE_SOIN = {"medecin", "estheticienne", "prestataire"}


def clinic_id_for(user: Any) -> int:
    """Extrait le clinic_id de l'utilisateur (dict ou ORM)."""
    if isinstance(user, dict):
        return int(user.get("clinic_id", 0))
    return int(getattr(user, "clinic_id", 0))


def require_clinic_context(user: Any) -> int:
    """Clinic_id obligatoire : sans contexte clinique, refus explicite."""
    clinic_id = clinic_id_for(user)
    if not clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Contexte clinique obligatoire",
        )
    return clinic_id


def role_of(user: Any) -> str:
    if isinstance(user, dict):
        return str(user.get("role", "")).replace("RoleEnum.", "").lower()
    return str(getattr(user, "role", "")).replace("RoleEnum.", "").lower()


def assert_clinic_scope(user: Any, clinic_id: int) -> None:
    """Refuse l'accès si l'utilisateur appartient à une autre clinique."""
    user_clinic = clinic_id_for(user)
    if user_clinic != int(clinic_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ressource hors périmètre de la clinique",
        )


def is_intervention_owner(user: Any, intervention: Any) -> bool:
    """Le professionnel de soin n'agit que sur ses propres interventions."""
    role = role_of(user)
    if role not in PROFESSIONNELS_DE_SOIN:
        return True  # direction/admin/assistante : contrôle par matrice
    user_id = int(user["id"]) if isinstance(user, dict) else int(user.id)
    return int(getattr(intervention, "professionnel_id", 0) or 0) == user_id


async def assert_intervention_scope(db: Any, user: Any, intervention_id: int) -> Any:
    """Charge l'intervention et vérifie clinique + affectation.

    Le backend refuse toute transition sur une intervention d'un collègue
    (critère Bloc 2 / Bloc 8 : contrôle côté backend).
    """
    from models.episode_core import Intervention
    from sqlalchemy import select

    result = await db.execute(
        select(Intervention).where(Intervention.id == intervention_id)
    )
    intervention = result.scalar_one_or_none()
    if intervention is None:
        raise HTTPException(status_code=404, detail="Intervention introuvable")

    assert_clinic_scope(user, intervention.clinic_id)

    role = role_of(user)
    if role in PROFESSIONNELS_DE_SOIN and not is_intervention_owner(user, intervention):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cette intervention est affectée à un autre professionnel",
        )
    return intervention


def filter_private_notes(user: Any, notes: list) -> list:
    """Filtre les notes privées selon le rôle.

    - médecin / direction / super_admin : toutes les notes ;
    - esthéticienne / prestataire : uniquement leurs notes ;
    - assistante / commercial / admin technique : aucune (jamais exposées).
    """
    role = role_of(user)
    if not can_access_private_notes(role):
        # La liste n'est PAS exposée : aucune fuite de métadonnées.
        return []

    if role in ("medecin", "directrice", "super_admin"):
        return notes

    user_id = int(user["id"]) if isinstance(user, dict) else int(user.id)
    return [n for n in notes if int(getattr(n, "auteur_id", 0) or 0) == user_id]


def price_policy(user: Any) -> dict:
    """Politique d'affichage des prix : le médecin AFFICHE sans modifier."""
    role = role_of(user)
    return {
        "view": can_view_prices(role),
        "edit": can_edit_prices(role),
        "message": "Le médecin peut afficher les prix mais ne peut pas les modifier"
        if role == "medecin" and can_view_prices(role)
        else None,
    }


def can(user: Any, resource: str, action: str) -> bool:
    """Wrapper courant : vérifie la matrice pour l'utilisateur connecté."""
    return check_permission(role_of(user), resource, action)


def can_bloc2(user: Any, action_name: str) -> bool:
    """Wrapper courant : vérifie une action nommée du Bloc 2."""
    from middleware.clinic_rbac import check_bloc2_action
    return check_bloc2_action(role_of(user), action_name)


def permission_summary(user: Any) -> dict:
    """Résumé complet pour /rbac/me (l'interface s'en sert uniquement pour
    construire les boutons — la sécurité reste côté backend)."""
    role = role_of(user)
    return {
        "role": role,
        "role_label": role,
        "permissions": get_role_permissions(role),
        "bloc2_actions": get_bloc2_permissions(role),
        "price": price_policy(user),
        "can_access_private_notes": can_access_private_notes(role),
        "can_manage_team": role in ("directrice", "admin", "super_admin"),
        "can_validate_financial": can_bloc2(user, "validate_financial"),
        "can_convert_devis": can_bloc2(user, "convert_devis"),
        "can_register_payment": can_bloc2(user, "register_payment"),
    }
