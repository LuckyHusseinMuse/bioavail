"""Shared test helpers. Lives in its own module so the signing key exists exactly once
(pytest imports conftest.py under its own name, which would otherwise create a second key)."""
import os
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

TEST_DB = os.environ.get("TEST_DATABASE_URL", "")
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_KEY = PRIVATE_KEY.public_key()
ISSUER = "https://absorb-test.eu.auth0.com/"
AUDIENCE = "https://api.absorb.test"


def make_token(sub: str, *, audience: str = AUDIENCE, issuer: str = ISSUER, expires_in: int = 3600, key=None) -> str:
    now = int(time.time())
    claims = {"sub": sub, "aud": audience, "iss": issuer, "iat": now, "exp": now + expires_in, "scope": "openid profile"}
    return jwt.encode(claims, key or PRIVATE_KEY, algorithm="RS256", headers={"kid": "test"})


def auth(sub: str) -> dict:
    return {"Authorization": f"Bearer {make_token(sub)}"}


needs_db = pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL not set")
