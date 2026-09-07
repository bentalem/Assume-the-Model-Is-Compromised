"""Shared fixtures.

These tests exercise the API's own logic — token verification, the policy client's deny behavior,
field minimization, error shapes. The database and OPA are stubbed here; their real behavior is
proven by the database smoke tests and the OPA policy tests, and end to end by verify-local.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

ISSUER = "http://keycloak:8080/realms/supportpilot"
AUDIENCE = "supportpilot-api"

ALICE_SUB = "alice-id"
ALICE_UUID = "a1111111-1111-1111-1111-111111111111"
CEDAR = "11111111-1111-1111-1111-111111111111"
NORTHWIND = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(scope="session")
def signing_key() -> dict[str, Any]:
    """An RSA key pair, in the JWK shape Keycloak publishes."""
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
    """Mint a token, with any claim overridable so negative cases are one keyword away."""

    def _make(**overrides: Any) -> str:
        now = int(time.time())
        claims = {
            "sub": ALICE_SUB,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + 300,
            "jti": "token-1",
            "typ": "Bearer",
            "acr": "2",
            "scope": "openid profile",
        }
        claims.update(overrides)
        headers = {"kid": overrides.pop("_kid", signing_key["kid"])}
        algorithm = overrides.pop("_alg", "RS256")
        return jwt.encode(
            claims, signing_key["private_pem"], algorithm=algorithm, headers=headers
        )

    return _make


class StubJwks:
    def __init__(self, jwk_dict: dict[str, Any]) -> None:
        self._jwk = jwk_dict
        self.fetch_count = 0

    def get(self, kid: str) -> dict[str, Any] | None:
        self.fetch_count += 1
        return self._jwk if kid == self._jwk["kid"] else None

    def invalidate(self) -> None:
        pass


@pytest.fixture
def jwks(signing_key) -> StubJwks:
    return StubJwks(signing_key["public_jwk"])


@pytest.fixture
def verifier(jwks):
    from supportpilot_api.auth.tokens import TokenVerifier

    return TokenVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=jwks, leeway_seconds=5)
