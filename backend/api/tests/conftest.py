"""API test setup.

- Environment variables override backend/.env, so tests never touch Tiger Data or real Auth0/Gemini.
- Auth0 is simulated with a locally generated RSA key (api/tests/helpers.py).
- DB-backed tests use TEST_DATABASE_URL (local TimescaleDB) and are skipped without it.
"""
import os

import pytest

from api.tests.helpers import PUBLIC_KEY, TEST_DB

os.environ.update({
    "DATABASE_URL": TEST_DB,
    "AUTH0_DOMAIN": "absorb-test.eu.auth0.com",
    "AUTH0_AUDIENCE": "https://api.absorb.test",
    "AUTH_DEV_SECRET": "",
    "GEMINI_API_KEY": "",
})

from fastapi.testclient import TestClient  # noqa: E402

from api.settings import get_settings  # noqa: E402

get_settings.cache_clear()

from api.auth import get_key_resolver  # noqa: E402
from api.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    app.dependency_overrides[get_key_resolver] = lambda: (lambda token, settings: PUBLIC_KEY)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
