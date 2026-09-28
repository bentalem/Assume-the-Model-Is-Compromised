"""Shared fixtures for the broker's tests.

The scope table and the profiles are the repository's real files, not copies: a test that passed
against a fixture while the real ceiling said something else would prove nothing. Keycloak and the
API are stood in for — a key pair in Keycloak's JWK shape, and an in-process API that records what
it was sent.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jose import jwk, jwt

from delegation_broker.main import Broker
from delegation_broker.tokens import Minter, SigningKey, UserVerifier
from delegation_broker.trusted import load_profiles, load_scopes

REPO = Path(__file__).resolve().parents[3]
KEYCLOAK = "https://keycloak:8443/realms/supportpilot"
BROKER = "http://broker:8097"
AUDIENCE = "supportpilot-api"
ALICE_SUB = "alice-keycloak-sub"


def _pem(private) -> str:
    return private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                 serialization.NoEncryption()).decode()


@pytest.fixture(scope="session")
def keycloak_key() -> dict[str, Any]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    public = jwk.construct(public_pem, algorithm="RS256").to_dict()
    public.update({"kid": "kc-1", "alg": "RS256"})
    return {"pem": _pem(private), "jwk": public, "kid": "kc-1"}


@pytest.fixture(scope="session")
def signing_pem() -> str:
    return _pem(ec.generate_private_key(ec.SECP256R1()))


@pytest.fixture(scope="session")
def other_signing_pem() -> str:
    return _pem(ec.generate_private_key(ec.SECP256R1()))


class StubKeys:
    def __init__(self, public: dict[str, Any]) -> None:
        self._public = public

    def get(self, kid: str) -> dict[str, Any] | None:
        return self._public if kid == self._public["kid"] else None


@pytest.fixture
def user_token(keycloak_key):
    """A Keycloak-shaped user token for alice, any claim overridable."""

    def _make(**overrides: Any) -> str:
        now = int(time.time())
        claims = {"iss": KEYCLOAK, "sub": ALICE_SUB, "aud": AUDIENCE, "iat": now,
                  "exp": now + 300, "typ": "Bearer", "acr": "1"}
        claims.update(overrides)
        return jwt.encode(claims, keycloak_key["pem"], algorithm="RS256",
                          headers={"kid": keycloak_key["kid"]})

    return _make


@pytest.fixture
def scopes():
    return load_scopes(REPO / "policy" / "supportpilot" / "scopes.json")


@pytest.fixture
def secrets_dir(tmp_path) -> Path:
    directory = tmp_path / "secrets"
    directory.mkdir()
    for name in ("status_helper", "refund_assistant"):
        (directory / f"broker_profile_{name}").write_text(f"{name}-test-credential")
    return directory


@pytest.fixture
def profiles(scopes, secrets_dir):
    return load_profiles(REPO / "infrastructure" / "local" / "broker" / "profiles.json",
                         secrets_dir, scopes)


@pytest.fixture
def settings_path(tmp_path) -> Path:
    return tmp_path / "settings.json"


@pytest.fixture
def arm(settings_path):
    def _arm(**switches: bool) -> None:
        settings_path.write_text(json.dumps({k.replace("_", "."): v for k, v in switches.items()}))
    return _arm


@pytest.fixture
def signing_key(signing_pem) -> SigningKey:
    return SigningKey(signing_pem)


@pytest.fixture
def minter(signing_key) -> Minter:
    return Minter(signing_key, issuer=BROKER, audience=AUDIENCE)


@pytest.fixture
def users(keycloak_key) -> UserVerifier:
    return UserVerifier(issuer=KEYCLOAK, audience=AUDIENCE, keys=StubKeys(keycloak_key["jwk"]))


class RecordingApi:
    """The API, in process: records each forwarded request and answers 200 with a small body."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json={"ok": True}, headers={"X-Request-Id": "req-upstream"})


@pytest.fixture
def api() -> RecordingApi:
    return RecordingApi()


@pytest.fixture
def broker(scopes, profiles, users, minter, signing_key, settings_path, api) -> Broker:
    return Broker(scopes=scopes, profiles=profiles, users=users, minter=minter,
                  signing_key=signing_key, api_url="http://api:8000", settings_path=settings_path,
                  transport=httpx.MockTransport(api.handler))


def claims_of(token: str) -> dict[str, Any]:
    return jwt.get_unverified_claims(token)


@pytest.fixture
def copy_profiles(tmp_path):
    """A writable copy of the real profiles file, for the tests that break it on purpose."""

    def _copy(mutate) -> Path:
        path = tmp_path / "profiles.json"
        shutil.copy(REPO / "infrastructure" / "local" / "broker" / "profiles.json", path)
        data = json.loads(path.read_text())
        mutate(data)
        path.write_text(json.dumps(data))
        return path

    return _copy
