"""The probe service.

The Range cannot reach the API, and that boundary is asserted (`V-17`). Twelve challenges still need
a learner to make a request *through* the API. This service is the answer: it can reach the API, it
holds one fixed list of requests, and the Range can ask it for one of them by name.

Read `docs/architecture/adr-0003-range-request-probes.md` for why this rather than the one-line fix
of putting the Range on the `app` network.

Three properties, in the order they matter:

  **No request comes from a caller.** There is no endpoint taking a method, a path, a header or a
  body. `POST /probe/{id}` looks the id up in a registry written by hand. A caller can choose from
  the list; it cannot extend it.

  **It refuses to start outside a local lab.** This service obtains tokens for five users. Anywhere
  but `local` that is a credential store with an HTTP interface, so it exits before binding a port.

  **It is not a general route to the API.** Bodies are not returned — only the status, the error
  code, and the field *names* present in the response. A challenge that needs data reads it from the
  database through a Range observation, where the row cap and field list are already enforced.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import sys

import httpx
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from .registry import ENUMERATIONS, PROBES, TAMPERED, WRONG_AUDIENCE

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("supportpilot.probe")

API_URL = os.environ.get("SUPPORTPILOT_API_URL", "http://api:8000")
KEYCLOAK = os.environ.get("KEYCLOAK_URL", "https://keycloak:8443")
REALM = os.environ.get("KEYCLOAK_REALM", "supportpilot")
CLIENT = os.environ.get("KEYCLOAK_CLIENT", "supportpilot-test-harness")


class EnvironmentRefused(RuntimeError):
    """Raised when the probe service is asked to run outside a local lab."""


def assert_local(environment: str | None = None) -> str:
    value = environment if environment is not None else os.environ.get("SUPPORTPILOT_ENV", "")
    if value != "local":
        raise EnvironmentRefused(
            f"SUPPORTPILOT_ENV is {value!r}; the probe service starts only when it is 'local'. "
            "It obtains tokens for every seeded lab user, which outside a lab is a credential "
            "store with an HTTP interface."
        )
    return value


def shared_secret() -> str:
    """The token the Range presents.

    Network placement alone cannot make the direction one-way: this service sits on `app` so that it
    can reach the API, and anything else on `app` can therefore open a socket to it. The secret is
    what makes "reachable" different from "usable", and it is mounted to exactly two services.
    """
    path = os.environ.get("PROBE_SHARED_SECRET_FILE", "/run/secrets/probe_shared_secret")
    try:
        return open(path, encoding="utf-8").read().strip()
    except OSError as exc:  # noqa: BLE001 — a probe with no secret must not run
        raise EnvironmentRefused(f"shared secret unreadable at {path}: {exc}") from exc


app = FastAPI(title="SupportPilot Probe", version="0.1.0",
              docs_url=None, redoc_url=None, openapi_url=None)

_secret = ""


@app.on_event("startup")
def startup() -> None:
    global _secret
    assert_local()
    _secret = shared_secret()
    logger.info("probe service ready with %d request(s) and %d tampered-token case(s)",
                len(PROBES), len(TAMPERED))


def _token_for(username: str, client: str | None = None) -> str:
    """Obtain a user token the way every other tool in this lab does.

    The password is the lab's fixed fixture pattern, the same one `scripts/abuse_suite.py` and
    `scripts/learn_identity.py` use. These are seeded users in a realm file committed to the
    repository — fixtures, not secrets — and the local-only guard above is what keeps that true.
    """
    response = httpx.post(
        f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": client or CLIENT,
            "username": username,
            "password": f"{username}-local-password",
            "scope": "openid",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["access_token"]


@app.get("/healthz", include_in_schema=False)
def healthz() -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "environment": os.environ.get("SUPPORTPILOT_ENV", ""),
            "probes": len(PROBES),
        }
    )


@app.get("/probes", include_in_schema=False)
def list_probes(x_range_token: str = Header(default="")) -> JSONResponse:
    if not secrets.compare_digest(x_range_token, _secret):
        return JSONResponse({"error": "unauthorised"}, status_code=401)
    return JSONResponse(
        {
            "probes": [
                {"id": p.id, "summary": p.summary, "user": p.user,
                 "request": f"{p.method} {p.path}", "intent": p.intent}
                for p in PROBES.values()
            ]
        }
    )


@app.post("/probe/{probe_id}", include_in_schema=False)
def run_probe(probe_id: str, request: Request, x_range_token: str = Header(default="")) -> JSONResponse:
    # Constant-time, because this is the only thing between anything else on `app` and a service
    # that can act as five users.
    if not secrets.compare_digest(x_range_token, _secret):
        logger.warning("rejected probe request with a bad token from %s", request.client)
        return JSONResponse({"error": "unauthorised"}, status_code=401)

    probe = PROBES.get(probe_id)
    if probe is None:
        return JSONResponse({"error": "unknown_probe", "probe": probe_id}, status_code=404)

    try:
        token = _token_for(probe.user)
    except Exception as exc:  # noqa: BLE001 — reported, never guessed at
        logger.exception("token acquisition failed for %s", probe.user)
        return JSONResponse(
            {"probe": probe.id, "user": probe.user, "error": f"token_failed: {type(exc).__name__}"},
            status_code=502,
        )

    # The body, when the registry declares one, is sent as the exact bytes written in that file.
    # Not json=..., which would re-serialise a structure this service had built: the probe that
    # needs a body needs the API to see a specific one, and re-encoding is how "a fixed request"
    # quietly becomes "a request this service composed".
    headers = {"Authorization": f"Bearer {token}"}
    content = None
    if probe.body is not None:
        headers["Content-Type"] = "application/json"
        content = probe.body.encode("utf-8")

    try:
        response = httpx.request(
            probe.method,
            f"{API_URL}{probe.path}",
            headers=headers,
            content=content,
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("probe request failed: %s", probe.id)
        return JSONResponse(
            {"probe": probe.id, "error": f"request_failed: {type(exc).__name__}"}, status_code=502
        )

    # What comes back, and deliberately no more. Field names, never values: a probe that returned
    # bodies would be a second, unbounded way to read the same data the observations already bound.
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {}

    error = body.get("error", {}) if isinstance(body, dict) else {}

    return JSONResponse(
        {
            "probe": probe.id,
            "user": probe.user,
            "request": f"{probe.method} {probe.path}",
            "intent": probe.intent,
            "status": response.status_code,
            "error_code": error.get("code", "") if isinstance(error, dict) else "",
            "request_id": response.headers.get("X-Request-Id", ""),
            "fields": sorted(body.keys()) if isinstance(body, dict) else [],
        }
    )


def run() -> None:
    import uvicorn

    try:
        assert_local()
        shared_secret()
    except EnvironmentRefused as exc:
        print(f"probe: {exc}", file=sys.stderr)
        raise SystemExit(78)  # EX_CONFIG

    uvicorn.run(
        app,
        host="0.0.0.0",  # noqa: S104 — never published; reachable only on internal networks
        port=int(os.environ.get("PORT", "8096")),
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )


# --------------------------------------------------------------------------------------------------
# Token transforms, for track 1.
#
# Each takes a genuine token and changes exactly one thing. Nothing here forges a signature the API
# would accept — that is the point: these are the attacks, and the API is supposed to refuse all of
# them. A transform that produced an accepted token would be a finding, not a challenge.
# --------------------------------------------------------------------------------------------------

def _b64url_decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def strip_signature(token: str) -> str:
    """`alg: none`. The oldest JWT attack, and still worth checking for."""
    header, payload, _ = token.split(".")
    new_header = _b64url_encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    return f"{new_header}.{payload}."


def resign_with_attacker_key(token: str) -> str:
    """Re-sign with HS256 and a key we chose.

    This is the algorithm-confusion shape: a verifier that trusts the header's `alg` and uses the
    issuer's *public* key as an HMAC secret would accept a token signed this way. One that pins the
    algorithm will not.
    """
    header, payload, _ = token.split(".")
    new_header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    signing_input = f"{new_header}.{payload}".encode()
    signature = hmac.new(b"attacker-chosen-key", signing_input, hashlib.sha256).digest()
    return f"{new_header}.{payload}.{_b64url_encode(signature)}"


def claim_other_organization(token: str) -> str:
    """Rewrite a tenant claim and re-sign with a key we chose.

    The claim is not one this API reads — tenancy comes from `app.memberships`, not from the token —
    so this fails twice over. Both refusals are worth seeing: the signature is checked first, and
    the claim would have changed nothing even if it had not been.
    """
    header, payload, _ = token.split(".")
    claims = json.loads(_b64url_decode(payload))
    claims["organization_id"] = "22222222-2222-2222-2222-222222222222"
    new_payload = _b64url_encode(json.dumps(claims).encode())
    return resign_with_attacker_key(f"{header}.{new_payload}.")


_TRANSFORMS = {
    "strip_signature": strip_signature,
    "resign_with_attacker_key": resign_with_attacker_key,
    "claim_other_organization": claim_other_organization,
}


@app.post("/enumerate/{enumeration_id}", include_in_schema=False)
def run_enumeration(
    enumeration_id: str, request: Request, x_range_token: str = Header(default="")
) -> JSONResponse:
    """Make the same permitted search repeatedly, following the cursor, and report counts.

    For challenge 4.3. Each call is inside the policy's page cap, made by a real user with a real
    role, and recorded as allowed. Nothing here is an exploit; the finding is what the calls add up
    to, and that nothing counts them.

    Counts only, never records. A probe that returned the pages would be exactly the bulk-read
    channel this challenge exists to describe.
    """
    if not secrets.compare_digest(x_range_token, _secret):
        logger.warning("rejected enumeration request with a bad token from %s", request.client)
        return JSONResponse({"error": "unauthorised"}, status_code=401)

    plan = ENUMERATIONS.get(enumeration_id)
    if plan is None:
        return JSONResponse(
            {"error": "unknown_enumeration", "enumeration": enumeration_id}, status_code=404
        )

    try:
        token = _token_for(plan.user)
    except Exception as exc:  # noqa: BLE001
        logger.exception("token acquisition failed for %s", plan.user)
        return JSONResponse(
            {"enumeration": plan.id, "error": f"token_failed: {type(exc).__name__}"},
            status_code=502,
        )

    seen: set[str] = set()
    cursor: str | None = None
    calls = 0
    statuses: set[int] = set()

    for _page in range(plan.max_pages):
        params = {"q": plan.query, "limit": "25"}
        if cursor:
            params["cursor"] = cursor
        try:
            response = httpx.get(
                f"{API_URL}{plan.path}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("enumeration request failed: %s", plan.id)
            return JSONResponse(
                {"enumeration": plan.id, "error": f"request_failed: {type(exc).__name__}"},
                status_code=502,
            )

        calls += 1
        statuses.add(response.status_code)
        if response.status_code != 200:
            break

        try:
            body = response.json()
        except json.JSONDecodeError:
            break

        for row in body.get("results", []):
            reference = row.get("customer_ref")
            if reference:
                seen.add(reference)

        cursor = body.get("next_cursor")
        if not cursor:
            break

    return JSONResponse(
        {
            "enumeration": plan.id,
            "user": plan.user,
            "query": plan.query,
            "intent": plan.intent,
            "calls": calls,
            "distinct_records": len(seen),
            "every_call_allowed": statuses == {200},
            "more_pages_remaining": bool(cursor),
        }
    )


@app.post("/tampered/{probe_id}", include_in_schema=False)
def run_tampered(probe_id: str, request: Request, x_range_token: str = Header(default="")) -> JSONResponse:
    if not secrets.compare_digest(x_range_token, _secret):
        return JSONResponse({"error": "unauthorised"}, status_code=401)

    entry = TAMPERED.get(probe_id)
    if entry is None:
        return JSONResponse({"error": "unknown_probe", "probe": probe_id}, status_code=404)

    user, transform_name, intent = entry
    try:
        token = _TRANSFORMS[transform_name](_token_for(user))
    except Exception as exc:  # noqa: BLE001
        logger.exception("could not build tampered token for %s", probe_id)
        return JSONResponse({"probe": probe_id, "error": f"build_failed: {type(exc).__name__}"},
                            status_code=502)

    try:
        response = httpx.get(
            f"{API_URL}/v1/orders/ORD-2001",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"probe": probe_id, "error": f"request_failed: {type(exc).__name__}"},
                            status_code=502)

    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {}
    error = body.get("error", {}) if isinstance(body, dict) else {}

    return JSONResponse(
        {
            "probe": probe_id,
            "user": f"{user} (tampered)",
            "request": "GET /v1/orders/ORD-2001",
            "intent": intent,
            "status": response.status_code,
            "error_code": error.get("code", "") if isinstance(error, dict) else "",
            "fields": sorted(body.keys()) if isinstance(body, dict) else [],
        }
    )


@app.post("/audience/{probe_id}", include_in_schema=False)
def run_wrong_audience(probe_id: str, x_range_token: str = Header(default="")) -> JSONResponse:
    """A valid token, minted for somebody else.

    Separate from `/tampered/` on purpose. Nothing here is forged, and a learner should be able to
    see from the id which kind of case they are running: one where the credential is broken, and one
    where the credential is perfect and was simply not meant for this service.
    """
    if not secrets.compare_digest(x_range_token, _secret):
        return JSONResponse({"error": "unauthorised"}, status_code=401)

    entry = WRONG_AUDIENCE.get(probe_id)
    if entry is None:
        return JSONResponse({"error": "unknown_probe", "probe": probe_id}, status_code=404)

    user, client, intent = entry
    try:
        token = _token_for(user, client=client)
    except Exception as exc:  # noqa: BLE001
        logger.exception("could not mint a token from %s", client)
        return JSONResponse({"probe": probe_id, "error": f"token_failed: {type(exc).__name__}"},
                            status_code=502)

    try:
        response = httpx.get(
            f"{API_URL}/v1/orders/ORD-2001",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"probe": probe_id, "error": f"request_failed: {type(exc).__name__}"},
                            status_code=502)

    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {}
    error = body.get("error", {}) if isinstance(body, dict) else {}

    # The audience claim is shown because it is the whole point, and because a learner should be
    # able to see that the token is otherwise entirely ordinary.
    try:
        claims = json.loads(_b64url_decode(token.split(".")[1]))
        audience = claims.get("aud", "(absent)")
    except Exception:  # noqa: BLE001
        audience = "(unreadable)"

    return JSONResponse(
        {
            "probe": probe_id,
            "user": f"{user} via {client}",
            "request": "GET /v1/orders/ORD-2001",
            "intent": f"{intent} aud={audience}",
            "status": response.status_code,
            "error_code": error.get("code", "") if isinstance(error, dict) else "",
            "fields": sorted(body.keys()) if isinstance(body, dict) else [],
        }
    )
