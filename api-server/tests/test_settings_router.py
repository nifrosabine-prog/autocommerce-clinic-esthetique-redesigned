"""Tests — api/v1/settings.py (via TestClient)"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from main import app
from api.deps import get_db, limiter
from api.v1.settings import ActeCreate


@pytest.fixture
def client(db):
    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_branding_is_public(client):
    r = client.get("/api/v1/settings/branding")
    assert r.status_code == 200
    assert "nom_clinique" in r.json()


def test_patch_branding_requires_auth(client):
    r = client.patch("/api/v1/settings/branding", json={"nom_clinique": "X"})
    assert r.status_code == 401


def test_acte_validation_rejects_blank_text_and_zero_price_when_not_free():
    with pytest.raises(ValidationError, match="au moins 2 caractères"):
        ActeCreate(nom="  ", categorie="soin", duree_minutes=30, prix_base="120")

    with pytest.raises(ValidationError, match="prix strictement supérieur à 0"):
        ActeCreate(nom="Consultation", categorie="soin", duree_minutes=30, prix_base="0", is_gratuit=False)


def test_acte_validation_allows_zero_price_only_when_explicitly_free():
    acte = ActeCreate(nom="  Soin   découverte ", categorie="  soin  ", duree_minutes=30, prix_base="0", is_gratuit=True)
    assert acte.nom == "Soin découverte"
    assert acte.categorie == "soin"
    assert acte.prix_base == 0


def test_public_callback_request_creates_pending_reminder(client):
    r = client.post("/api/v1/public/rappel", json={
        "nom": "Demande Test",
        "telephone": "+21699887766",
        "message": "Merci de me rappeler pour une consultation.",
    })
    assert r.status_code == 201
    assert r.json()["statut"] == "pending"
    assert r.json()["lead_id"] > 0


def test_public_reservation_endpoint_reachable_without_auth(client, medecin, acte):
    r = client.post("/api/v1/public/reservation", json={
        "nom": "Test", "prenom": "Public", "telephone": "+21699887766",
        "praticien_id": medecin.id, "acte_id": acte.id,
        "date_heure": (datetime(2026, 7, 20, 15, 0)).isoformat(),
    })
    assert r.status_code == 202
    assert r.json()["statut"] == "pending"
    assert "booking_request_id" in r.json()


@pytest.mark.asyncio
async def test_public_reservation_is_rate_limited(client, medecin, acte):
    limiter.enabled = True
    limiter.reset()
    try:
        for i in range(5):
            r = client.post("/api/v1/public/reservation", json={
                "nom": "Test", "prenom": "Public", "telephone": f"+2169988776{i}",
                "praticien_id": medecin.id, "acte_id": acte.id,
                "date_heure": (datetime(2026, 7, 20, 9, 0) + timedelta(hours=i)).isoformat(),
            })
            assert r.status_code == 202

        r = client.post("/api/v1/public/reservation", json={
            "nom": "Test", "prenom": "Public", "telephone": "+21699887799",
            "praticien_id": medecin.id, "acte_id": acte.id,
            "date_heure": (datetime(2026, 7, 20, 20, 0)).isoformat(),
        })
        assert r.status_code == 429
    finally:
        limiter.enabled = False
