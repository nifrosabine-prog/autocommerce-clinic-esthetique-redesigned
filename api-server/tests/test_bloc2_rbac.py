"""
Tests Bloc 2 — matrice RBAC stricte, rôle PRESTATAIRE, permissions métier.

Vérifie les critères d'acceptation du Bloc 2 :
  - actions interdites → erreur backend explicite (403) ;
  - portée clinique et portée d'intervention (professionnel non affecté) ;
  - notes privées jamais exposées aux rôles non autorisés ;
  - le médecin AFFICHE les prix sans pouvoir les modifier ;
  - tests de permissions par rôle (backend, pas seulement frontend).
"""

import pytest
from fastapi import HTTPException

from middleware.clinic_rbac import (
    RESOURCE_PERMISSIONS,
    BLOC2_ACTIONS,
    check_permission,
    check_bloc2_action,
    require_role,
    require_permission,
    can_view_prices,
    can_edit_prices,
    can_access_private_notes,
    get_bloc2_permissions,
)
from models.database import RoleEnum, Utilisateur
from services.rbac_service import (
    clinic_id_for,
    require_clinic_context,
    assert_clinic_scope,
    is_intervention_owner,
    filter_private_notes,
    price_policy,
    permission_summary,
)


# ── 1. Matrice : règles métier critiques ────────────────────

@pytest.mark.parametrize("role", ["assistante", "commercial", "prestataire"])
def test_non_medical_roles_have_no_access_to_dossiers_medicaux(role):
    assert check_permission(role, "dossiers_medicaux", "read") is False
    assert check_permission(role, "dossiers_medicaux", "write") is False


def test_assistante_has_no_access_to_photos_medicales():
    assert check_permission("assistante", "photos", "read") is False


def test_directrice_read_only_on_dossiers():
    assert check_permission("directrice", "dossiers_medicaux", "read") is True
    assert check_permission("directrice", "dossiers_medicaux", "write") is False


def test_medecin_full_access_to_dossiers():
    assert check_permission("medecin", "dossiers_medicaux", "read") is True
    assert check_permission("medecin", "dossiers_medicaux", "write") is True
    assert check_permission("medecin", "dossiers_medicaux", "delete") is False


# ── 2. Bloc 2 : l'admin technique n'a PAS l'accès médical ────

def test_admin_technique_no_automatic_medical_access():
    """Critère Bloc 2 : ne pas considérer qu'un rôle technique possède
    automatiquement l'accès aux données médicales."""
    # Photos : refus systématique.
    assert check_permission("admin", "photos", "read") is False
    assert check_permission("admin", "photos", "write") is False
    # Notes privées : refus systématique.
    assert check_permission("admin", "notes_privees", "read") is False
    assert check_permission("admin", "notes_privees", "write") is False
    # Dossiers médicaux : lecture technique auditée, jamais en écriture.
    assert check_permission("admin", "dossiers_medicaux", "read") is True
    assert check_permission("admin", "dossiers_medicaux", "write") is False


def test_admin_keeps_technical_permissions():
    """L'admin conserve la gestion technique (hors médical)."""
    assert check_permission("admin", "settings", "write") is True
    assert check_permission("admin", "patients", "read") is True
    assert check_permission("admin", "stock_injectables", "write") is True


# ── 3. Notes privées : jamais exposées aux rôles non autorisés ──

def test_private_notes_never_exposed_to_unauthorized_roles():
    for role in ("assistante", "commercial", "admin"):
        assert check_permission(role, "notes_privees", "read") is False


def test_private_notes_authorized_roles():
    assert check_permission("medecin", "notes_privees", "read") is True
    assert check_permission("directrice", "notes_privees", "read") is True


def test_filter_private_notes_no_leak_for_assistante():
    notes = [{"auteur_id": 1, "contenu": "privé"}]
    assert filter_private_notes({"id": 9, "role": "assistante"}, notes) == []


def test_filter_private_notes_estheticienne_only_her_own():
    notes = [type("N", (), {"auteur_id": 2})(), type("N", (), {"auteur_id": 5})()]
    result = filter_private_notes({"id": 2, "role": "estheticienne"}, notes)
    assert len(result) == 1
    assert result[0].auteur_id == 2


# ── 4. Prix : le médecin AFFICHE sans modifier ───────────────

def test_medecin_can_view_prices_but_never_edit():
    assert can_view_prices("medecin") is True
    assert can_edit_prices("medecin") is False
    policy = price_policy({"role": "medecin"})
    assert policy["view"] is True
    assert policy["edit"] is False


def test_prix_masques_par_defaut_autres_roles():
    # Esthéticienne et prestataire : prix masqués par défaut.
    assert can_view_prices("estheticienne") is False
    assert can_view_prices("prestataire") is False
    # L'assistante et la direction voient et modifient.
    assert can_edit_prices("assistante") is True
    assert can_edit_prices("directrice") is True


# ── 5. Actions Bloc 2 (mapping nommé) ────────────────────────

BLOC2_EXPECTATIONS = {
    "admin_data": {"directrice", "medecin", "estheticienne", "assistante", "commercial", "admin", "prestataire", "super_admin"},
    "read_medical": {"directrice", "medecin", "estheticienne", "admin", "super_admin"},
    "write_medical": {"medecin", "estheticienne"},
    "access_private_notes": {"medecin", "directrice", "super_admin", "estheticienne", "prestataire"},
    "create_shared_note": {"directrice", "medecin", "estheticienne", "prestataire", "super_admin"},
    "create_intervention": {"medecin", "estheticienne", "prestataire"},
    "start_intervention": {"medecin", "estheticienne", "prestataire"},
    "validate_intervention": {"medecin", "estheticienne", "prestataire", "directrice"},
    "propose_actes": {"medecin", "estheticienne", "prestataire"},
    "view_price": {"medecin", "directrice", "assistante", "admin", "super_admin"},
    "edit_price": {"directrice", "assistante", "admin", "super_admin"},
    "apply_remise": {"directrice", "assistante", "admin", "super_admin"},
    "validate_financial": {"directrice", "assistante", "super_admin"},
    "convert_devis": {"directrice", "assistante", "super_admin"},
    "register_payment": {"directrice", "assistante", "admin", "super_admin"},
    "access_photos": {"medecin", "estheticienne", "super_admin"},
    "run_simulation_ia": {"medecin", "directrice", "admin", "super_admin"},
    "use_lot": {"directrice", "medecin", "estheticienne", "admin", "prestataire", "super_admin"},
    "close_episode": {"directrice", "medecin"},
}

@pytest.mark.parametrize("action_name", list(BLOC2_EXPECTATIONS))
def test_bloc2_action_mapping(action_name):
    """Chaque action nommée du cahier des charges permet exactement les
    rôles attendus (énumération exhaustive dans le test)."""
    expected = BLOC2_EXPECTATIONS[action_name]
    for role in ("directrice", "medecin", "estheticienne", "assistante", "commercial", "admin", "prestataire", "super_admin"):
        assert check_bloc2_action(role, action_name) is (role in expected), (
            f"{action_name}: rôle {role} attendu {role in expected}"
        )


def test_all_bloc2_actions_are_defined_in_matrix():
    """Chaque action Bloc 2 doit pointer vers une resource+action existante."""
    for action_name, (resource, action) in BLOC2_ACTIONS.items():
        assert resource in RESOURCE_PERMISSIONS, f"{action_name} → resource inconnue {resource}"
        # Au moins un rôle possède l'action (sinon l'entrée est morte).
        assert any(action in perms for perms in RESOURCE_PERMISSIONS[resource].values())


# ── 6. Rôle PRESTATAIRE (masseuse) ───────────────────────────

def test_prestataire_scope_interventions():
    """Le prestataire (masseuse) ne voit que les données de son intervention."""
    assert check_permission("prestataire", "interventions", "start") is True
    assert check_permission("prestataire", "interventions", "validate") is True
    assert check_permission("prestataire", "interventions", "read") is True
    # Pas d'accès financier.
    assert check_permission("prestataire", "prix", "read") is False
    assert check_permission("prestataire", "devis", "read") is False
    assert check_permission("prestataire", "paiements", "read") is False
    # Pas d'accès à l'historique médical complet.
    assert check_permission("prestataire", "dossiers_medicaux", "read") is False


def test_prestataire_own_intervention_only():
    class Intervention:
        def __init__(self, professionnel_id):
            self.professionnel_id = professionnel_id

    user = {"id": 7, "role": "prestataire"}
    assert is_intervention_owner(user, Intervention(7)) is True
    assert is_intervention_owner(user, Intervention(3)) is False


# ── 7. require_permission : erreur backend explicite ─────────

@pytest.mark.asyncio
async def test_require_permission_grants_medecin_dossier_write():
    checker = require_permission("dossiers_medicaux", "write")
    mock_user = type("U", (), {"id": 1, "role": "medecin", "clinic_id": 1, "is_active": True})()
    user = await checker(current_user=mock_user)
    assert user.role == "medecin"


@pytest.mark.asyncio
async def test_require_permission_forbids_assistante_dossier_write():
    checker = require_permission("dossiers_medicaux", "write")
    mock_user = type("U", (), {"id": 2, "role": "assistante", "clinic_id": 1, "is_active": True})()
    with pytest.raises(HTTPException) as exc:
        await checker(current_user=mock_user)
    assert exc.value.status_code == 403
    assert "dossiers_medicaux" in exc.value.detail


@pytest.mark.asyncio
async def test_require_permission_forbids_admin_photos():
    """Bloc 2 : l'admin technique n'a pas l'accès photos."""
    checker = require_permission("photos", "read")
    mock_user = type("U", (), {"id": 3, "role": "admin", "clinic_id": 1, "is_active": True})()
    with pytest.raises(HTTPException) as exc:
        await checker(current_user=mock_user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_keeps_legacy_behavior():
    checker = require_role(RoleEnum.MEDECIN)
    mock_user = type("U", (), {"id": 1, "role": "medecin", "clinic_id": 1})()
    user = await checker(current_user=mock_user)
    assert user.role == "medecin"


@pytest.mark.asyncio
async def test_require_role_still_rejects():
    checker = require_role(RoleEnum.MEDECIN)
    mock_user = type("U", (), {"id": 2, "role": "assistante", "clinic_id": 1})()
    with pytest.raises(HTTPException) as exc:
        await checker(current_user=mock_user)
    assert exc.value.status_code == 403


# ── 8. Contexte clinique (multi-clinique) ────────────────────

def test_require_clinic_context_rejects_without_clinic():
    with pytest.raises(HTTPException) as exc:
        require_clinic_context({"id": 1, "role": "medecin"})
    assert exc.value.status_code == 403
    assert "Contexte clinique" in exc.value.detail


def test_assert_clinic_scope_rejects_other_clinic():
    with pytest.raises(HTTPException) as exc:
        assert_clinic_scope({"id": 1, "clinic_id": 1, "role": "medecin"}, 2)
    assert exc.value.status_code == 403


def test_clinic_id_for():
    assert clinic_id_for({"clinic_id": 3}) == 3


# ── 9. Résumé / aide d'interface ─────────────────────────────

def test_permission_summary_medecin():
    summary = permission_summary({"id": 1, "clinic_id": 1, "role": "medecin"})
    assert summary["role"] == "medecin"
    assert summary["price"]["view"] is True
    assert summary["price"]["edit"] is False
    assert summary["can_validate_financial"] is False
    assert summary["can_register_payment"] is False
    assert "write_medical" in summary["bloc2_actions"]


def test_permission_summary_assistante_has_finance():
    summary = permission_summary({"id": 2, "clinic_id": 1, "role": "assistante"})
    assert summary["can_validate_financial"] is True
    assert summary["can_convert_devis"] is True
    assert summary["can_register_payment"] is True
    assert summary["can_access_private_notes"] is False


def test_get_bloc2_permissions_admin_has_no_medical():
    perms = set(get_bloc2_permissions("admin"))
    # L'admin technique : jamais de notes privées, jamais de photos, jamais
    # d'écriture médicale. La lecture technique des dossiers concerne les
    # lignes chiffrées et reste auditée.
    assert "access_private_notes" not in perms
    assert "access_photos" not in perms
    assert "write_medical" not in perms
    assert "edit_price" in perms
