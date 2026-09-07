"""TS-1 — Token and identity.

Every case here must reject *before* policy or database access. The verifier has no database or
policy dependency at all, which is how that property is guaranteed rather than asserted.
"""

from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

from supportpilot_api.auth.tokens import bearer_from_header

from .conftest import ALICE_SUB, AUDIENCE, ISSUER


def assert_rejected(verifier, token: str) -> None:
    with pytest.raises(HTTPException) as exc:
        verifier.verify(token)
    assert exc.value.status_code == 401
    assert exc.value.detail == "unauthenticated"


# TS1-01 -------------------------------------------------------------------------------------
def test_valid_token_is_accepted(verifier, make_token):
    result = verifier.verify(make_token())
    assert result.subject == ALICE_SUB
    assert result.is_mfa is True


# TS1-02 -------------------------------------------------------------------------------------
def test_token_signed_by_unknown_key_is_rejected(verifier, make_token, signing_key):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jose import jwt

    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = other.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    now = int(time.time())
    forged = jwt.encode(
        {"sub": ALICE_SUB, "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 300},
        pem,
        algorithm="RS256",
        headers={"kid": signing_key["kid"]},  # claims a key id we do trust
    )
    assert_rejected(verifier, forged)


def test_unknown_key_id_is_rejected(verifier, make_token):
    assert_rejected(verifier, make_token(_kid="rotated-away"))


# TS1-03 -------------------------------------------------------------------------------------
def test_alg_none_is_rejected(verifier):
    # Hand-built unsigned token: header {"alg":"none"}, empty signature.
    import base64
    import json

    def b64(data: dict) -> str:
        raw = json.dumps(data).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    now = int(time.time())
    token = (
        b64({"alg": "none", "kid": "test-key-1"})
        + "."
        + b64({"sub": ALICE_SUB, "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 300})
        + "."
    )
    assert_rejected(verifier, token)


def test_symmetric_algorithm_is_rejected(verifier, signing_key):
    """An HS256 token must not be verifiable, even with a correct-looking key id."""
    import base64
    import json

    def b64(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    now = int(time.time())
    unsigned = (
        b64({"alg": "HS256", "kid": signing_key["kid"]})
        + "."
        + b64({"sub": ALICE_SUB, "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 300})
        + ".c2ln"
    )
    assert_rejected(verifier, unsigned)


# TS1-04 / TS1-05 ----------------------------------------------------------------------------
def test_wrong_issuer_is_rejected(verifier, make_token):
    assert_rejected(verifier, make_token(iss="http://evil.invalid/realms/supportpilot"))


def test_wrong_audience_is_rejected(verifier, make_token):
    assert_rejected(verifier, make_token(aud="some-other-api"))


def test_audience_list_without_our_audience_is_rejected(verifier, make_token):
    assert_rejected(verifier, make_token(aud=["other-api", "third-api"]))


def test_audience_list_containing_our_audience_is_accepted(verifier, make_token):
    assert verifier.verify(make_token(aud=["other-api", AUDIENCE])).subject == ALICE_SUB


# TS1-06 -------------------------------------------------------------------------------------
def test_expired_token_is_rejected(verifier, make_token):
    now = int(time.time())
    assert_rejected(verifier, make_token(iat=now - 600, exp=now - 300))


def test_not_yet_valid_token_is_rejected(verifier, make_token):
    now = int(time.time())
    assert_rejected(verifier, make_token(nbf=now + 600, exp=now + 900))


# TS1-07 -------------------------------------------------------------------------------------
def test_missing_expiry_is_rejected(verifier, signing_key):
    from jose import jwt

    now = int(time.time())
    token = jwt.encode(
        {"sub": ALICE_SUB, "iss": ISSUER, "aud": AUDIENCE, "iat": now},
        signing_key["private_pem"],
        algorithm="RS256",
        headers={"kid": signing_key["kid"]},
    )
    assert_rejected(verifier, token)


def test_missing_subject_is_rejected(verifier, make_token):
    assert_rejected(verifier, make_token(sub=""))


# TS1-08 -------------------------------------------------------------------------------------
def test_refresh_token_type_is_rejected(verifier, make_token):
    assert_rejected(verifier, make_token(typ="Refresh"))


def test_id_token_type_is_rejected(verifier, make_token):
    assert_rejected(verifier, make_token(typ="ID"))


# Malformed input ----------------------------------------------------------------------------
@pytest.mark.parametrize("value", ["", "not-a-token", "a.b", "a.b.c.d", "....", " "])
def test_malformed_tokens_are_rejected(verifier, value):
    assert_rejected(verifier, value)


# Header parsing -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "header",
    [None, "", "Basic dXNlcjpwYXNz", "Bearer", "Bearer   ", "Token abc", "bearer"],
)
def test_non_bearer_headers_are_rejected(header):
    with pytest.raises(HTTPException) as exc:
        bearer_from_header(header)
    assert exc.value.status_code == 401


def test_bearer_header_is_case_insensitive_in_scheme():
    assert bearer_from_header("bearer abc.def.ghi") == "abc.def.ghi"


# Authentication level -----------------------------------------------------------------------
def test_single_factor_is_not_reported_as_mfa(verifier, make_token):
    assert verifier.verify(make_token(acr="1", amr=["pwd"])).is_mfa is False


def test_amr_otp_counts_as_mfa(verifier, make_token):
    assert verifier.verify(make_token(acr="1", amr=["pwd", "otp"])).is_mfa is True


def test_unknown_acr_defaults_to_single_factor(verifier, make_token):
    """Anything not positively recognised is the weaker answer, never the stronger one."""
    assert verifier.verify(make_token(acr="something-new")).is_mfa is False
