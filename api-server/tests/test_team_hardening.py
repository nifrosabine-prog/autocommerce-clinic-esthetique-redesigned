"""Régression P0/P1 pour les comptes de l'équipe clinique."""

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from api.v1.users import UserCreate, UserUpdate, create_user, delete_user, update_user
from middleware.auth import get_password_hash
from models.database import AuditLogTeam, RoleEnum, Utilisateur


async def _director(db) -> Utilisateur:
    director = Utilisateur(
        clinic_id=1,
        email="direction@clinic.tn",
        hashed_password=get_password_hash("MotDePasse!23"),
        nom="Direction",
        prenom="Clinique",
        role=RoleEnum.DIRECTRICE.value,
        is_active=True,
    )
    db.add(director)
    await db.flush()
    return director


@pytest.mark.asyncio
async def test_reactivation_is_persisted_for_each_clinic_role(db):
    actor = await _director(db)
    roles = (
        RoleEnum.MEDECIN,
        RoleEnum.ASSISTANTE,
        RoleEnum.COMMERCIAL,
        RoleEnum.ESTHETICIENNE,
    )

    for index, role in enumerate(roles):
        user = Utilisateur(
            clinic_id=1,
            email=f"inactif-{index}@clinic.tn",
            hashed_password=get_password_hash("MotDePasse!23"),
            nom="Compte",
            prenom=role.value,
            role=role.value,
            is_active=False,
        )
        db.add(user)
    await db.flush()

    inactive_users = (
        await db.execute(
            select(Utilisateur).where(
                Utilisateur.email.like("inactif-%@clinic.tn")
            )
        )
    ).scalars().all()
    for user in inactive_users:
        result = await update_user(
            user.id,
            UserUpdate(is_active=True),
            db,
            {"id": actor.id, "role": actor.role, "clinic_id": 1},
        )
        assert result["is_active"] is True

    audit_count = await db.scalar(
        select(func.count(AuditLogTeam.id)).where(
            AuditLogTeam.action == "activation",
            AuditLogTeam.utilisateur_id.in_([user.id for user in inactive_users]),
        )
    )
    assert audit_count is not None


@pytest.mark.asyncio
async def test_clinic_cannot_remove_last_active_leader_or_create_admin(db):
    actor = await _director(db)
    target = Utilisateur(
        clinic_id=1,
        email="admin@clinic.tn",
        hashed_password="hashed",
        nom="Admin",
        prenom="Unique",
        role=RoleEnum.ADMIN.value,
        is_active=True,
    )
    db.add(target)
    await db.flush()
    current = {"id": actor.id, "role": actor.role, "clinic_id": 1}

    with pytest.raises(HTTPException) as exc:
        await update_user(target.id, UserUpdate(is_active=False), db, current)
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        await delete_user(target.id, db, current)
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        await create_user(
            UserCreate(
                email="admin-2@clinic.tn",
                nom="Admin",
                prenom="Deux",
                password="MotDePasse!23",
                role=RoleEnum.ADMIN,
            ),
            db,
            current,
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_is_logical_anonymized_and_audited(db):
    actor = await _director(db)
    member = Utilisateur(
        clinic_id=1,
        email="membre@clinic.tn",
        hashed_password="hashed",
        nom="Ben",
        prenom="Ali",
        role=RoleEnum.MEDECIN.value,
        is_active=True,
    )
    db.add(member)
    await db.flush()

    await delete_user(
        member.id,
        db,
        {"id": actor.id, "role": actor.role, "clinic_id": 1},
    )

    persisted = await db.scalar(select(Utilisateur).where(Utilisateur.id == member.id))
    assert persisted is not None
    assert persisted.is_active is False
    assert persisted.email.endswith("@anonymized.invalid")
    audit = await db.scalar(
        select(AuditLogTeam).where(
            AuditLogTeam.utilisateur_id == member.id,
            AuditLogTeam.action == "suppression",
        )
    )
    assert audit is not None
    assert audit.valeur_avant["email"] == "membre@clinic.tn"