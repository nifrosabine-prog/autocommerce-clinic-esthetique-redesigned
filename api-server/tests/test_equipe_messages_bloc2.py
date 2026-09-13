import pytest

from models.database import EquipeMessage, Utilisateur, RoleEnum
from services.notification_equipe import envoyer_messages


@pytest.mark.asyncio
async def test_envoie_a_plusieurs_destinataires_sans_doublons(db, medecin, assistante):
    messages = await envoyer_messages(
        db,
        expediteur_id=medecin.id,
        destinataire_ids=[assistante.id, assistante.id],
        sujet="Réunion",
        contenu="À demain.",
        clinic_id=1,
    )

    assert len(messages) == 1
    assert messages[0].destinataire_id == assistante.id
    assert messages[0].sujet == "Réunion"
    assert messages[0].contenu == "À demain."


@pytest.mark.asyncio
async def test_envoi_idempotent_reutilise_les_lignes_existantes(db, medecin, assistante):
    payload = dict(
        db=db,
        expediteur_id=medecin.id,
        destinataire_ids=[assistante.id],
        sujet="Suivi",
        contenu="Contenu unique",
        clinic_id=1,
        idempotency_key="bloc2-test-key",
    )
    first = await envoyer_messages(**payload)
    second = await envoyer_messages(**payload)

    assert [message.id for message in second] == [message.id for message in first]
    rows = (await db.execute(EquipeMessage.__table__.select())).all()
    assert len(rows) == 1  # aucune seconde ligne de message n’est créée


@pytest.mark.asyncio
async def test_refuse_membre_inactif_sans_envoi_partiel(db, medecin, assistante):
    assistante.is_active = False
    await db.flush()

    with pytest.raises(ValueError, match="introuvables, inactifs"):
        await envoyer_messages(
            db,
            expediteur_id=medecin.id,
            destinataire_ids=[assistante.id],
            sujet="Sujet",
            contenu="Message",
            clinic_id=1,
        )

    rows = (await db.execute(EquipeMessage.__table__.select())).all()
    assert rows == []


@pytest.mark.asyncio
async def test_refuse_destinataire_d_un_autre_tenant(db, medecin, assistante):
    other_clinic_user = Utilisateur(
        clinic_id=2,
        email="autre-clinique@clinic.tn",
        hashed_password="x",
        nom="Autre",
        prenom="Clinique",
        role=RoleEnum.MEDECIN.value,
    )
    db.add(other_clinic_user)
    await db.flush()

    with pytest.raises(ValueError, match="introuvables, inactifs"):
        await envoyer_messages(
            db,
            expediteur_id=medecin.id,
            destinataire_ids=[assistante.id, other_clinic_user.id],
            sujet="Sujet",
            contenu="Message",
            clinic_id=1,
        )
