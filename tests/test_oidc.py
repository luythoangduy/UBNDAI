import time

import pytest

from src.services.oidc import OIDCValidationError, validate_claims


def test_oidc_claim_validation_rejects_missing_provider_config(monkeypatch):
    monkeypatch.setattr("src.services.oidc.settings.oidc_issuer_url", "")
    with pytest.raises(OIDCValidationError):
        validate_claims({"sub": "citizen-1", "exp": int(time.time()) + 300})


def test_oidc_claim_validation_requires_mfa_and_verified_audience(monkeypatch):
    monkeypatch.setattr("src.services.oidc.settings.oidc_issuer_url", "https://idp.example")
    monkeypatch.setattr("src.services.oidc.settings.oidc_client_id", "portal")
    base = {"iss": "https://idp.example", "aud": "portal", "sub": "citizen-1", "exp": int(time.time()) + 300}
    with pytest.raises(OIDCValidationError):
        validate_claims(base)
    assert validate_claims({**base, "amr": ["pwd", "mfa"]})["sub"] == "citizen-1"
