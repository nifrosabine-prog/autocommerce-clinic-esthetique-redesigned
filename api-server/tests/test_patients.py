"""Tests — services/patients.py"""
import pytest

from services.patients import (
    create_patient, get_patient, list_patients, update_patient, anonymize_patient,
)
from models.database import Patient, Utilisateur, RoleEnum


@pytest.mark.asyncio
async def test_create_patient_encrypts_sensitive_fields(db):
    p = await create_patient({
        "nom": "Sassi", "prenom": "Amal", "telephone": "+21622111222",
        "allergies": "Pénicilline",
    }, db, {"role": "medecin", "id": 1, "clinic_id": 1})
    assert p["allergies"] == "Pénicilline"

    result = await db.get(Patient, p["id"])
    assert result.allergies_enc != "Pénicilline"


@pytest.mark.asyncio
async def test_create_patient_rejects_duplicate_phone(db):
    await create_patient({"nom": "A", "prenom": "B", "telephone": "+21600000000"}, db)
    with pytest.raises(ValueError, match="existe déjà"):
        await create_patient({"nom": "C", "prenom": "D", "telephone": "+21600000000"}, db)


@pytest.mark.asyncio
async def test_get_patient_denies_unrelated_commercial(db):
    other_commercial = Utilisateur(clinic_id=1, email="c2@clinic.tn", hashed_password="x",
                                    nom="X", prenom="Y", role=RoleEnum.COMMERCIAL.value)
    db.add(other_commercial)
    await db.flush()

    p = await create_patient({"nom": "E", "prenom": "F", "telephone": "+21611111111"}, db, {"role": "medecin", "id": 1, "clinic_id": 1})

    with pytest.raises(PermissionError):
        await get_patient(p["id"], {"role": "commercial", "id": other_commercial.id, "clinic_id": 1}, db)


@pytest.mark.asyncio
async def test_get_patient_allows_assigned_commercial(db):
    commercial = Utilisateur(clinic_id=1, email="c3@clinic.tn", hashed_password="x",
                              nom="X", prenom="Y", role=RoleEnum.COMMERCIAL.value)
    db.add(commercial)
    await db.flush()

    p = await create_patient({"nom": "G", "prenom": "H", "telephone": "+21622222222",
                               "commercial_id": commercial.id}, db, {"role": "medecin", "id": 1, "clinic_id": 1})

    result = await get_patient(p["id"], {"role": "commercial", "id": commercial.id, "clinic_id": 1}, db)
    assert result["id"] == p["id"]


@pytest.mark.asyncio
async def test_get_patient_hides_sensitive_fields_from_commercial(db, patient):
    patient.commercial_id = 1
    await db.flush()
    result = await get_patient(patient.id, {"role": "commercial", "id": 1, "clinic_id": 1}, db)
    assert "allergies" not in result


@pytest.mark.asyncio
async def test_get_patient_hides_sensitive_fields_from_assistante(db, patient):
    result = await get_patient(patient.id, {"role": "assistante", "id": 1, "clinic_id": 1}, db)
    assert "allergies" not in result


@pytest.mark.asyncio
async def test_get_patient_shows_sensitive_fields_to_medecin(db, patient):
    result = await get_patient(patient.id, {"role": "medecin", "id": 1, "clinic_id": 1}, db)
    assert "allergies" in result


@pytest.mark.asyncio
async def test_list_patients_scopes_to_own_commercial(db):
    commercial = Utilisateur(clinic_id=1, email="c4@clinic.tn", hashed_password="x",
                              nom="X", prenom="Y", role=RoleEnum.COMMERCIAL.value)
    db.add(commercial)
    await db.flush()

    await create_patient({"nom": "Mine", "prenom": "A", "telephone": "+21633333333",
                           "commercial_id": commercial.id}, db, {"role": "medecin", "id": 1, "clinic_id": 1})
    await create_patient({"nom": "NotMine", "prenom": "B", "telephone": "+21644444444"}, db, {"role": "medecin", "id": 1, "clinic_id": 1})

    results = await list_patients({"role": "commercial", "id": commercial.id, "clinic_id": 1}, db)
    assert len(results) == 1
    assert results[0]["nom"] == "Mine"


@pytest.mark.asyncio
async def test_list_patients_excludes_anonymized(db, patient):
    await anonymize_patient(patient.id, db)
    results = await list_patients({"role": "admin", "id": 1}, db)
    assert patient.id not in [p["id"] for p in results]


@pytest.mark.asyncio
async def test_update_patient_re_encrypts_field(db, patient):
    updated = await update_patient(patient.id, {"antecedents_medicaux": "Diabète type 2"},
                                    {"role": "medecin", "id": 1}, db)
    assert updated["antecedents_medicaux"] == "Diabète type 2"


@pytest.mark.asyncio
async def test_anonymize_patient_strips_identifying_data(db, patient):
    result = await anonymize_patient(patient.id, db)
    assert result["nom"] == "Anonymisé"
    assert result["anonymized_at"] is not None

    await db.refresh(patient)
    assert patient.email is None
    assert patient.allergies_enc is None
    assert patient.is_active is False


@pytest.mark.asyncio
async def test_anonymize_unknown_patient_raises(db):
    with pytest.raises(ValueError, match="non trouvé"):
        await anonymize_patient(999999, db)


@pytest.mark.asyncio
async def test_create_patient_allows_assistante_without_sensitive_fields(db):
    result = await create_patient(
        {"nom": "Accueil", "prenom": "Audit", "telephone": "+21629999999"},
        db,
        {"role": "assistante", "id": 1, "clinic_id": 1},
    )
    assert result["nom"] == "Accueil"
    assert "allergies" not in result
    assert "antecedents_medicaux" not in result


# ── Correctif 2026-09-11 : recherche par nom/téléphone pour tous les rôles ──

@pytest.mark.asyncio
async def test_list_patients_search_by_partial_phone_for_every_role(db, patient):
    """Téléphone du fixture : +21620000000 — une recherche sur un fragment
    (« 20000000 ») doit retrouver la patiente pour chaque rôle autorisé,
    y compris l'assistante et l'esthéticienne."""
    for role in ("assistante", "medecin", "estheticienne", "directrice", "admin"):
        results = await list_patients(
            {"role": role, "id": 1, "clinic_id": 1}, db, search="20000000"
        )
        assert patient.id in [p["id"] for p in results], f"recherche en échec pour {role}"


@pytest.mark.asyncio
async def test_list_patients_search_by_partial_name_for_assistante(db, patient):
    """« harb » (fragment casse-insensible de « Gharbi ») retrouve la patiente."""
    results = await list_patients(
        {"role": "assistante", "id": 1, "clinic_id": 1}, db, search="harb"
    )
    assert patient.id in [p["id"] for p in results]


@pytest.mark.asyncio
async def test_list_patients_search_covers_whatsapp_phone(db, patient):
    """Le numéro WhatsApp distinct du téléphone principal est recherchable."""
    patient.whatsapp_phone = "+21699999999"
    await db.flush()
    for role in ("medecin", "assistante"):
        results = await list_patients(
            {"role": role, "id": 1, "clinic_id": 1}, db, search="99999999"
        )
        assert patient.id in [p["id"] for p in results], f"recherche WhatsApp en échec pour {role}"


@pytest.mark.asyncio
async def test_list_patients_search_commercial_limited_to_own_patients(db):
    """La recherche élargie ne modifie pas le périmètre du commercial : il ne
    retrouve que ses propres patientes."""
    commercial = Utilisateur(clinic_id=1, email="c9@clinic.tn", hashed_password="x",
                              nom="X", prenom="Y", role=RoleEnum.COMMERCIAL.value)
    db.add(commercial)
    await db.flush()

    mine = await create_patient({"nom": "Mienne", "prenom": "A", "telephone": "+21655500001",
                                 "commercial_id": commercial.id}, db, {"role": "medecin", "id": 1, "clinic_id": 1})
    await create_patient({"nom": "Autre", "prenom": "B", "telephone": "+21655500002"}, db,
                         {"role": "medecin", "id": 1, "clinic_id": 1})

    results = await list_patients(
        {"role": "commercial", "id": commercial.id, "clinic_id": 1}, db, search="5550000"
    )
    ids = [p["id"] for p in results]
    assert mine["id"] in ids
    assert len(ids) == 1


# ── Recette 2026-09-11 : recherche nom / téléphone ACTIVE pour tous les rôles ──
# La recherche est filtrée côté serveur (jamais uniquement interface) ; le
# téléphone est comparé en chiffres seuls, quel que soit le format saisi ou
# stocké. Le périmètre (clinic_id, périmètre commercial) s'applique AVANT.

ALL_SEARCH_ROLES = ("assistante", "medecin", "estheticienne", "directrice", "admin")


@pytest.mark.asyncio
async def test_list_patients_search_by_name_for_every_role(db, patient):
    """« Gharbi Ines » est retrouvée par nom (partiel, casse-insensible) par
    chaque rôle autorisé, y compris l'assistante et l'esthéticienne."""
    for role in ALL_SEARCH_ROLES:
        for fragment in ("harb", "GHARBI", "ines"):
            results = await list_patients(
                {"role": role, "id": 1, "clinic_id": 1}, db, search=fragment
            )
            assert patient.id in [p["id"] for p in results], (
                f"recherche nom « {fragment} » en échec pour {role}"
            )


@pytest.mark.asyncio
async def test_list_patients_search_by_phone_digits_ignores_format(db, patient):
    """Le téléphone est cherché en chiffres seuls : « +216 20 000 000 »,
    « 00216.20.000.000 » et « 20000000 » retrouvent la même patiente,
    quel que soit le rôle — le format de saisie n'est jamais un obstacle."""
    patient.telephone = "+216 20 000 000"
    patient.whatsapp_phone = "00 216 20 000 000"
    await db.flush()

    for role in ALL_SEARCH_ROLES:
        for fragment in ("20000000", "+216 20 000 000", "00216.20.000.000"):
            results = await list_patients(
                {"role": role, "id": 1, "clinic_id": 1}, db, search=fragment
            )
            assert patient.id in [p["id"] for p in results], (
                f"recherche téléphone « {fragment} » en échec pour {role}"
            )


@pytest.mark.asyncio
async def test_list_patients_search_by_name_returns_no_medical_fields_for_restricted_roles(db, patient):
    """La recherche élargie aux rôles n'élargit PAS les champs médicaux :
    l'assistante et l'esthéticienne retrouvent la patiente par nom ou
    téléphone, mais restent soumises au masquage des champs sensibles."""
    patient.commercial_id = 1  # le périmètre du commercial reste ses propres patientes
    await db.flush()

    for role in ("assistante", "commercial", "directrice"):
        results = await list_patients(
            {"role": role, "id": 1, "clinic_id": 1}, db, search="Gharbi"
        )
        assert patient.id in [p["id"] for p in results], f"recherche nom en échec pour {role}"
        serialized = next(p for p in results if p["id"] == patient.id)
        assert "allergies" not in serialized
        assert "antecedents_medicaux" not in serialized


@pytest.mark.asyncio
async def test_list_patients_search_never_escapes_clinic_scope(db, patient):
    """La recherche ne franchit jamais la frontière de la clinique : une
    patiente homonyme d'une autre clinique n'est jamais renvoyée."""
    other = Patient(
        clinic_id=2, nom="Gharbi", prenom="Ines",
        telephone="+21628888888", whatsapp_phone="+21628888888",
    )
    db.add(other)
    await db.flush()

    results = await list_patients({"role": "medecin", "id": 1, "clinic_id": 1}, db, search="Gharbi")
    ids = [p["id"] for p in results]
    assert patient.id in ids
    assert other.id not in ids


@pytest.mark.asyncio
async def test_list_patients_search_is_case_insensitive_on_phone_with_country_code(db, patient):
    """Recherche par indicatif pays partiel (« 216 ») : elle retrouve la
    patiente car les chiffres du numéro sont recherchables en sous-chaîne."""
    for role in ALL_SEARCH_ROLES:
        results = await list_patients(
            {"role": role, "id": 1, "clinic_id": 1}, db, search="216"
        )
        assert patient.id in [p["id"] for p in results], f"recherche 216 en échec pour {role}"
