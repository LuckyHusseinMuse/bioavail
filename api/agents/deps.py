"""Who is calling? Uses Person A's Auth0 JWT validation (api/auth.py) when it exists.

Person A: export a FastAPI dependency `get_current_user` from api/auth.py that validates the
Auth0 access token and returns a dict with at least "sub". The agents use `sub` as user_id.
Until then, a DEV-ONLY stand-in returns a fixed demo user. It refuses to run if
ENV=production so it can never ship by accident.
"""
from __future__ import annotations

import os

from fastapi import Depends, HTTPException

try:
    from api.auth import get_current_user  # type: ignore[import-not-found]  # Person A
except ModuleNotFoundError:
    def get_current_user() -> dict:  # type: ignore[misc]
        if os.getenv("ENV") == "production":
            raise HTTPException(500, "api/auth.py missing: refusing to run without Auth0 validation")
        return {"sub": "demo|1"}


def current_user_id(user: dict = Depends(get_current_user)) -> str:
    sub = user.get("sub") if isinstance(user, dict) else getattr(user, "sub", None)
    if not sub:
        raise HTTPException(401, "no user")
    return sub
