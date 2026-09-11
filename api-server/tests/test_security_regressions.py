"""Régressions de sécurité issues de l’audit externe."""

import pytest

from fastapi import HTTPException

from api.v1.users import _validate_clinic_assignable_role, _validate_public_practitioner
from models.database import RoleEnum


def test_clinic_admin_cannot_assign_super_admin_role():
    with pytest.raises(HTTPException) as exc_info:
        _validate_clinic_assignable_role(RoleEnum.SUPER_ADMIN)
    assert exc_info.value.status_code == 403


def test_clinic_roles_remain_assignable():
    for role in (RoleEnum.ADMIN, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.ASSISTANTE):
        _validate_clinic_assignable_role(role)


def test_public_practitioner_must_have_an_active_clinical_role():
    with pytest.raises(HTTPException) as non_clinical:
        _validate_public_practitioner(role=RoleEnum.ASSISTANTE, is_active=True, is_public=True)
    assert non_clinical.value.status_code == 422

    with pytest.raises(HTTPException) as inactive:
        _validate_public_practitioner(role=RoleEnum.MEDECIN, is_active=False, is_public=True)
    assert inactive.value.status_code == 422


def test_active_clinical_practitioner_can_be_published():
    _validate_public_practitioner(role=RoleEnum.MEDECIN, is_active=True, is_public=True)
