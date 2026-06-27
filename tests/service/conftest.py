"""
Shared fixtures for service route tests.

All tests run against the real FastAPI app but with the DB layer patched out
so no DATABASE_URL is needed in CI.
"""
from __future__ import annotations

import os

import pytest

# Must be set before importing the app so psycopg2 doesn't fail at import time
# if any module does a top-level connect call (currently none do, but defensive).
os.environ.setdefault("DATABASE_URL", "postgresql://mock:mock@localhost/mock")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-placeholder")

from fastapi.testclient import TestClient  # noqa: E402

from lightningfish_service.main import app  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
