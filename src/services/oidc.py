"""Provider-neutral OIDC claim validation.

Signature/JWKS verification belongs to the OIDC client callback; this module
validates the verified claims before mapping them into application identities.
"""

from datetime import datetime, UTC
from typing import Any

from src.config import settings


class OIDCValidationError(ValueError):
    pass


def validate_claims(claims: dict[str, Any]) -> dict[str, Any]:
    if not settings.oidc_issuer_url or not settings.oidc_client_id:
        raise OIDCValidationError("OIDC is not configured")
    if claims.get("iss") != settings.oidc_issuer_url:
        raise OIDCValidationError("Invalid OIDC issuer")
    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    if settings.oidc_client_id not in audiences and (settings.oidc_audience and settings.oidc_audience not in audiences):
        raise OIDCValidationError("Invalid OIDC audience")
    if not claims.get("sub"):
        raise OIDCValidationError("OIDC subject is required")
    if int(claims.get("exp", 0)) <= int(datetime.now(UTC).timestamp()):
        raise OIDCValidationError("OIDC token expired")
    if settings.oidc_required_mfa_claim == "amr:mfa" and "mfa" not in set(claims.get("amr", [])):
        raise OIDCValidationError("MFA claim is required")
    return claims


def assert_production_config() -> None:
    if settings.app_env == "production" and (settings.enable_demo_auth or not settings.oidc_issuer_url or not settings.oidc_client_id):
        raise RuntimeError("Production requires OIDC configuration and demo auth disabled")
