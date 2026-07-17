"""Internal HMAC-signed access tokens for the local officer portal."""

import base64
import hashlib
import hmac
import json
import time

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

try:
    from jose import JWTError, jwt as jose_jwt
except ImportError:  # pragma: no cover - local minimal environment fallback
    JWTError = ValueError
    jose_jwt = None

from src.config import settings
from src.models import OfficerIdentity, TokenClaims

_bearer = HTTPBearer(auto_error=False)
_USERS = {
    "officer.demo": OfficerIdentity(user_id="officer-demo", organization_id="org-demo", roles={"officer_reviewer"}),
    "officer.other": OfficerIdentity(user_id="officer-other", organization_id="org-other", roles={"officer_reviewer"}),
    "citizen.demo": OfficerIdentity(user_id="citizen-demo", organization_id="public", roles={"citizen"}),
    "citizen.other": OfficerIdentity(user_id="citizen-other", organization_id="public", roles={"citizen"}),
}
_PASSWORD_HASH = hashlib.pbkdf2_hmac("sha256", settings.demo_password.encode(), b"ubndai-demo", 120_000)


def verify_credentials(username: str, password: str) -> OfficerIdentity | None:
    if not settings.enable_demo_auth:
        return None
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), b"ubndai-demo", 120_000)
    identity = _USERS.get(username)
    return identity if identity and hmac.compare_digest(candidate, _PASSWORD_HASH) else None


def issue_token(identity: OfficerIdentity) -> str:
    payload = {"user_id": identity.user_id, "organization_id": identity.organization_id, "roles": sorted(identity.roles), "exp": int(time.time()) + settings.jwt_access_ttl_minutes * 60}
    if jose_jwt is not None:
        return jose_jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(hmac.new(settings.jwt_secret.encode(), raw.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    return f"{raw}.{signature}"


def decode_token(token: str) -> TokenClaims:
    try:
        if jose_jwt is not None:
            return TokenClaims.model_validate(jose_jwt.decode(token, settings.jwt_secret, algorithms=["HS256"]))
        raw, signature = token.split(".", 1)
        expected = base64.urlsafe_b64encode(hmac.new(settings.jwt_secret.encode(), raw.encode(), hashlib.sha256).digest()).decode().rstrip("=")
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        claims = TokenClaims.model_validate(payload)
        if claims.exp <= int(time.time()):
            raise ValueError
        return claims
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token") from exc


def current_claims(credentials: HTTPAuthorizationCredentials | None = Security(_bearer)) -> TokenClaims:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return decode_token(credentials.credentials)


def require_role(*roles: str):
    def dependency(claims: TokenClaims = Security(current_claims)) -> TokenClaims:
        if not set(roles).intersection(claims.roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return claims
    return dependency
