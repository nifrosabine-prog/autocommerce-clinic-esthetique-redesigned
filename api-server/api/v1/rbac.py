"""
AutoCommerce Clinic — API RBAC (Bloc 2)

Expose à l'interface la matrice de permissions et le résumé du rôle
connecté. Aucune décision de sécurité ne repose sur ces lectures : les
vraies vérifications se font dans les endpoints métier via
require_permission / require_role (backend).

Routes :
  GET /rbac/me          → résumé des permissions de l'utilisateur connecté
  GET /rbac/matrix      → matrice complète (direction / admin / super_admin)
  GET /rbac/check       → vérification unitaire ?resource=&action=
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from middleware.auth import get_current_active_user
from middleware.clinic_rbac import (
    RESOURCE_PERMISSIONS,
    BLOC2_ACTIONS,
    check_permission,
    _to_role_enum,
)
from services.rbac_service import permission_summary, role_of

router = APIRouter(prefix="/rbac", tags=["rbac"])

MATRIX_ROLES = {"directrice", "admin", "super_admin"}


def _matrix_serializable() -> dict:
    """Matrice JSON : clés de rôle sous forme de valeurs lisibles."""
    return {
        resource: {
            role.value: actions
            for role, actions in perms.items()
        }
        for resource, perms in RESOURCE_PERMISSIONS.items()
    }


@router.get("/me")
async def rbac_me(
    current_user: dict = Depends(get_current_active_user),
) -> dict:
    """Permissions de l'utilisateur connecté (aide d'interface uniquement)."""
    return permission_summary(current_user)


@router.get("/matrix")
async def rbac_matrix(
    current_user: dict = Depends(get_current_active_user),
) -> dict:
    """Matrice complète réservée à la direction et aux administrateurs."""
    role = role_of(current_user)
    if role not in MATRIX_ROLES:
        raise HTTPException(status_code=403, detail="Accès refusé : matrice réservée")
    return {
        "matrix": _matrix_serializable(),
        "bloc2_actions": BLOC2_ACTIONS,
    }


@router.get("/check")
async def rbac_check(
    resource: str = Query(..., min_length=1, max_length=100),
    action: str = Query(..., min_length=1, max_length=100),
    current_user: dict = Depends(get_current_active_user),
) -> dict:
    """Vérification unitaire : l'utilisateur a-t-il (resource, action) ?"""
    role = role_of(current_user)
    allowed = check_permission(role, resource, action)
    return {
        "role": role,
        "resource": resource,
        "action": action,
        "allowed": allowed,
        "detail": "Autorisé" if allowed else f"Action '{action}' refusée pour le rôle {role}",
    }
