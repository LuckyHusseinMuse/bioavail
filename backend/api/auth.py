"""Server-side authentication (ProjectDefinition.md section 7.3).

The signed-in user comes only from a verified token. Endpoints and agent tools receive `User` from here and
never accept a user ID from the request body or from model output.

Modes
- auth0: RS256 tokens verified against https://{AUTH0_DOMAIN}/.well-known/jwks.json, audience and issuer checked.
- dev:   HS256 tokens signed with AUTH_DEV_SECRET (local development before Auth0 is set up).
         Mint one with: python -m api.auth dev-user-1
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.settings import Settings, get_settings

bearer = HTTPBearer(auto_error=False)
_jwks_clients: dict[str, jwt.PyJWKClient] = {}


@dataclass(frozen=True)
class User:
    user_id: str
    scopes: frozenset[str] = field(default_factory=frozenset)


def _unauthorised(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def signing_key_for(token: str, settings: Settings):
    """Public key for an Auth0 token (cached JWKS). Tests override this dependency."""
    url = f"https://{settings.auth0_domain}/.well-known/jwks.json"
    client = _jwks_clients.setdefault(url, jwt.PyJWKClient(url, cache_keys=True, lifespan=3600))
    return client.get_signing_key_from_jwt(token).key


def verify_token(token: str, settings: Settings, key_resolver=signing_key_for) -> User:
    try:
        if settings.auth_mode == "auth0":
            key = key_resolver(token, settings)
            claims = jwt.decode(token, key, algorithms=["RS256"], audience=settings.auth0_audience,
                                issuer=f"https://{settings.auth0_domain}/")
        elif settings.auth_mode == "dev":
            claims = jwt.decode(token, settings.auth_dev_secret, algorithms=["HS256"], audience="absorb-dev")
        else:
            raise _unauthorised("Authentication is not configured on the server")
    except jwt.ExpiredSignatureError as e:
        raise _unauthorised("Token expired") from e
    except jwt.PyJWTError as e:
        raise _unauthorised("Invalid token") from e   # no internals in the response
    sub = claims.get("sub")
    if not sub:
        raise _unauthorised("Token has no subject")
    scopes = frozenset((claims.get("scope") or "").split())
    return User(user_id=sub, scopes=scopes)


def get_key_resolver():
    return signing_key_for


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
    key_resolver=Depends(get_key_resolver),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorised("Missing bearer token")
    return verify_token(creds.credentials, settings, key_resolver)


def mint_dev_token(user_id: str, secret: str, hours: float = 24) -> str:
    now = int(time.time())
    return jwt.encode({"sub": user_id, "aud": "absorb-dev", "iat": now, "exp": now + int(hours * 3600)},
                      secret, algorithm="HS256")


if __name__ == "__main__":
    import sys

    s = get_settings()
    if not s.auth_dev_secret:
        sys.exit("Set AUTH_DEV_SECRET in backend/.env first")
    print(mint_dev_token(sys.argv[1] if len(sys.argv) > 1 else "dev|user-1", s.auth_dev_secret))
