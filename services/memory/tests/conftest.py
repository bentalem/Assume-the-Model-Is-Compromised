"""Shared fixtures for the memory service's unit tests.

These exercise the service's own logic: token verification against the memory audience, principal
resolution, the secret filter, how request context is set, and the error model. The databases are
stubbed, exactly as the API's tests stub theirs.

What these tests deliberately do NOT claim to prove is isolation. Row-level security lives in
memory-db, and a stub cannot enforce it — a test that faked it would be testing the fake. Isolation
is proven by memory-db's smoke tests (run by memory-init on every start) and by
scripts/memory_suite.py against the running stack, where the cross-tenant cases are.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

ISSUER = "http://keycloak:8080/realms/supportpilot"
MEMORY_AUDIENCE = "supportpilot-memory"
API_AUDIENCE = "supportpilot-api"
ALICE_SUB = "alice-id"
CEDAR = "11111111-1111-1111-1111-111111111111"
NORTHWIND = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(scope="session")
def signing_key() -> dict[str, Any]:
    from jose import jwk

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_jwk = jwk.construct(public_pem, algorithm="RS256").to_dict()
    public_jwk["kid"] = "test-key-1"
    public_jwk["alg"] = "RS256"
    return {"private_pem": private_pem.decode(), "public_jwk": public_jwk, "kid": "test-key-1"}


@pytest.fixture
def make_token(signing_key):
    """Mint a token; any claim overridable so a negative case is one keyword away."""

    def _make(**overrides: Any) -> str:
        now = int(time.time())
        claims = {
            "sub": ALICE_SUB, "iss": ISSUER, "aud": [MEMORY_AUDIENCE, API_AUDIENCE],
            "iat": now, "exp": now + 300, "jti": "t-1", "typ": "Bearer",
        }
        claims.update({k: v for k, v in overrides.items() if not k.startswith("_")})
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, signing_key["private_pem"],
                          algorithm=overrides.get("_alg", "RS256"),
                          headers={"kid": overrides.get("_kid", signing_key["kid"])})

    return _make


class StubJwks:
    def __init__(self, jwk_dict: dict[str, Any]) -> None:
        self._jwk = jwk_dict

    def get(self, kid: str) -> dict[str, Any] | None:
        return self._jwk if kid == self._jwk["kid"] else None


@pytest.fixture
def verifier(signing_key):
    from supportpilot_memory.tokens import TokenVerifier

    return TokenVerifier(issuer=ISSUER, audience=MEMORY_AUDIENCE,
                         jwks=StubJwks(signing_key["public_jwk"]))


class RecordingCursor:
    """A cursor that records every statement and answers from a script."""

    def __init__(self, answers: dict[str, Any] | None = None) -> None:
        self.executed: list[tuple[str, tuple]] = []
        self._answers = answers or {}
        self._last = None

    def execute(self, query: str, params: tuple = ()) -> None:
        self.executed.append((query, params))
        self._last = next((v for k, v in self._answers.items() if k in query), None)

    def fetchone(self):
        return self._last

    def fetchall(self):
        return self._last or []


class StubPrincipals:
    def __init__(self, principal=None, error=None) -> None:
        self._principal = principal
        self._error = error
        self.calls: list[str] = []

    def resolve(self, subject: str):
        self.calls.append(subject)
        if self._error:
            raise self._error
        return self._principal

    def healthy(self) -> bool:
        return True


class StubDb:
    def __init__(self, cursor: RecordingCursor | None = None) -> None:
        self.cursor = cursor or RecordingCursor()
        self.principals_seen: list[Any] = []

    @contextmanager
    def transaction(self, principal):
        self.principals_seen.append(principal)
        yield self.cursor

    def healthy(self) -> bool:
        return True


@pytest.fixture
def alice():
    from supportpilot_memory.principal import Principal

    return Principal(subject=ALICE_SUB, user_id="a1111111-1111-1111-1111-111111111111",
                     org_id=CEDAR, roles=("support_agent",))


@pytest.fixture
def client(verifier, alice):
    """A TestClient over the real application, with stubbed stores and a real verifier."""
    from fastapi.testclient import TestClient

    from supportpilot_memory.config import Settings
    from supportpilot_memory.main import Services, create_app

    settings = Settings(environment="local", issuer=ISSUER, jwks_url="http://unused",
                        audience=MEMORY_AUDIENCE, token_leeway_seconds=30,
                        mem_db_host="x", mem_db_port=5432, mem_db_name="x", mem_db_user="x",
                        mem_db_password="x")
    services = Services(settings=settings, db=StubDb(), principals=StubPrincipals(alice),
                        verifier=verifier, extras={})
    app = create_app(settings=settings, services=services)
    # The lifespan would open real pools; the stubs need none.
    app.router.lifespan_context = _no_lifespan
    return TestClient(app, raise_server_exceptions=False)


@asynccontextmanager
async def _no_lifespan(app):
    yield
