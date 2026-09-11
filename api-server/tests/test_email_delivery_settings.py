import pytest
from pydantic import ValidationError

from api.v1.settings import EmailDeliverySettingsUpdate


def test_email_delivery_byok_accepts_matching_sender_domain():
    payload = EmailDeliverySettingsUpdate(
        provider="resend",
        sending_domain="Clinique-Exemple.TLD",
        from_email="Contrats@Clinique-Exemple.TLD",
    )

    assert payload.sending_domain == "clinique-exemple.tld"
    assert payload.from_email == "contrats@clinique-exemple.tld"


def test_email_delivery_byok_rejects_sender_from_other_domain():
    with pytest.raises(ValidationError, match="doit utiliser le domaine"):
        EmailDeliverySettingsUpdate(
            provider="resend",
            sending_domain="clinique-exemple.tld",
            from_email="contrats@autre-clinique.tld",
        )


def test_email_delivery_byok_rejects_url_instead_of_domain():
    with pytest.raises(ValidationError, match="nom de domaine valide"):
        EmailDeliverySettingsUpdate(
            provider="resend",
            sending_domain="https://clinique-exemple.tld/portail",
            from_email="contrats@clinique-exemple.tld",
        )
