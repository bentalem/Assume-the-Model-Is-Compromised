"""Who the memory service believes is calling, and what it refuses to believe."""

from __future__ import annotations

import psycopg
import pytest

from supportpilot_memory.errors import ApiError
from supportpilot_memory.principal import PrincipalResolver

from .conftest import ALICE_SUB, API_AUDIENCE, CEDAR, MEMORY_AUDIENCE, NORTHWIND

# ------------------------------------------------------------------------------------------------
# Tokens. The verifier is the API's, copied; what is under test here is the audience.
# ------------------------------------------------------------------------------------------------


def test_accepts_a_token_carrying_the_memory_audience(verifier, make_token):
    assert verifier.verify(make_token()).subject == ALICE_SUB


def test_accepts_a_token_whose_only_audience_is_memory(verifier, make_token):
    assert verifier.verify(make_token(aud=MEMORY_AUDIENCE)).subject == ALICE_SUB


def test_refuses_a_token_minted_only_for_the_api(verifier, make_token):
    """Challenge 1.2, applied to a second resource server: genuine, and for somebody else."""
    with pytest.raises(ApiError) as exc:
        verifier.verify(make_token(aud=API_AUDIENCE))
    assert exc.value.status_code == 401


def test_refuses_a_token_with_no_audience(verifier, make_token):
    with pytest.raises(ApiError):
        verifier.verify(make_token(aud=None))


def test_refuses_alg_none(verifier, make_token, signing_key):
    token = make_token()
    header, body, _ = token.split(".")
    import base64
    import json

    forged_header = base64.urlsafe_b64encode(
        json.dumps({"alg": "none", "kid": signing_key["kid"]}).encode()
    ).decode().rstrip("=")
    with pytest.raises(ApiError):
        verifier.verify(f"{forged_header}.{body}.")


def test_refuses_an_expired_token(verifier, make_token):
    with pytest.raises(ApiError):
        verifier.verify(make_token(exp=1, iat=0))


# ------------------------------------------------------------------------------------------------
# Principal resolution. The rows are what app.resolve_subject returns.
# ------------------------------------------------------------------------------------------------


class _Cursor:
    def __init__(self, rows=None, error=None):
        self._rows, self._error = rows or [], error
        self.executed = []

    def execute(self, query, params):
        self.executed.append((query, params))
        if self._error:
            raise self._error

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Conn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Pool:
    def __init__(self, cursor):
        self._cursor = cursor

    def connection(self, timeout=None):
        return _Conn(self._cursor)


def _resolver(rows=None, error=None):
    resolver = PrincipalResolver.__new__(PrincipalResolver)
    cursor = _Cursor(rows, error)
    resolver._pool = _Pool(cursor)
    return resolver, cursor


def _row(org, role, user="a1111111-1111-1111-1111-111111111111"):
    return {"user_id": user, "organization_id": org, "role": role}


def test_resolves_one_organisation_and_its_roles():
    resolver, cursor = _resolver([_row(CEDAR, "support_agent"), _row(CEDAR, "auditor")])
    principal = resolver.resolve(ALICE_SUB)
    assert principal.org_id == CEDAR
    assert principal.roles == ("auditor", "support_agent")
    # The subject is passed as a bound parameter to the one function the role may call.
    assert cursor.executed == [(
        "SELECT user_id, organization_id, role FROM app.resolve_subject(%s)", (ALICE_SUB,)
    )]


def test_an_unknown_subject_is_not_found():
    resolver, _ = _resolver([])
    with pytest.raises(ApiError) as exc:
        resolver.resolve("nobody")
    assert exc.value.status_code == 404


def test_a_user_with_no_active_membership_is_not_found():
    resolver, _ = _resolver([_row(None, None)])
    with pytest.raises(ApiError) as exc:
        resolver.resolve(ALICE_SUB)
    assert exc.value.status_code == 404


def test_two_organisations_are_refused_rather_than_guessed_between():
    """Nothing in a request may choose the tenant, so there is nothing to choose it with."""
    resolver, _ = _resolver([_row(CEDAR, "support_manager"), _row(NORTHWIND, "support_manager")])
    with pytest.raises(ApiError) as exc:
        resolver.resolve("agent-service")
    assert exc.value.status_code == 403
    assert exc.value.code == "ambiguous_tenant"


def test_an_unreachable_identity_store_denies():
    """Deny by default: never 'proceed without knowing whose memories these are'."""
    resolver, _ = _resolver(error=psycopg.OperationalError("down"))
    with pytest.raises(ApiError) as exc:
        resolver.resolve(ALICE_SUB)
    assert exc.value.status_code == 503


def test_every_request_asks_again():
    """Never cached — a demoted role must stop working on the next request (challenge 1.3)."""
    resolver, cursor = _resolver([_row(CEDAR, "support_manager")])
    resolver.resolve(ALICE_SUB)
    resolver.resolve(ALICE_SUB)
    assert len(cursor.executed) == 2
