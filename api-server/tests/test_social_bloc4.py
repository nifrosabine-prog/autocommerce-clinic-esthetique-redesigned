from api.v1.social import _SOCIAL_READ_ROLES, router
from models.database import RoleEnum


def _route(path: str, method: str):
    for route in router.routes:
        if getattr(route, "path", None) == f"/social{path}" and method in getattr(route, "methods", set()):
            return route
    raise AssertionError(f"route introuvable: {method} {path}")


def _dependency_names(route):
    return {
        getattr(dependency.call, "__name__", "")
        for dependency in route.dependant.dependencies
    }


def test_social_read_roles_include_practitioner_and_esthetician():
    assert RoleEnum.MEDECIN in _SOCIAL_READ_ROLES
    assert RoleEnum.ESTHETICIENNE in _SOCIAL_READ_ROLES


def test_social_read_routes_use_the_clinic_role_gate():
    for path in ("/messages", "/posts", "/analytics", "/avis"):
        route = _route(path, "GET")
        assert "role_checker" in _dependency_names(route)


def test_social_write_routes_remain_role_gated():
    for path, method in (
        ("/messages/{message_id}/repondre", "POST"),
        ("/posts", "POST"),
        ("/posts/{post_id}/publier", "POST"),
        ("/avis/{avis_id}/valider", "POST"),
    ):
        route = _route(path, method)
        assert "role_checker" in _dependency_names(route)
