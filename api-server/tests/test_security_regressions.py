"""Régressions de sécurité issues de l’audit externe."""

import pytest

from fastapi import HTTPException

from api.v1.users import _validate_clinic_assignable_role
from models.database import RoleEnum


def test_clinic_admin_cannot_assign_super_admin_role():
    with pytest.raises(HTTPException) as exc_info:
        _validate_clinic_assignable_role(RoleEnum.SUPER_ADMIN)
    assert exc_info.value.status_code == 403


def test_clinic_roles_remain_assignable():
    # Rôles attribuables depuis la gestion d'équipe d'une clinique
    # (ADMIN est volontairement exclu : rôle technique plateforme).
    for role in (RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.ASSISTANTE, RoleEnum.COMMERCIAL):
        _validate_clinic_assignable_role(role)


def test_clinic_cannot_assign_admin_role():
    with pytest.raises(HTTPException) as exc_info:
        _validate_clinic_assignable_role(RoleEnum.ADMIN)
    assert exc_info.value.status_code == 403
