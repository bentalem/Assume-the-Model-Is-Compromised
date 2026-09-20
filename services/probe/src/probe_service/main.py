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

import json
import logging
import os
import secrets
import sys

import httpx
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from .registry import PROBES

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
    logger.info("probe service ready with %d registered request(s)", len(PROBES))


def _token_for(username: str) -> str:
    """Obtain a user token the way every other tool in this lab does.

    The password is the lab's fixed fixture pattern, the same one `scripts/abuse_suite.py` and
    `scripts/learn_identity.py` use. These are seeded users in a realm file committed to the
    repository — fixtures, not secrets — and the local-only guard above is what keeps that true.
    """
    response = httpx.post(
        f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": CLIENT,
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

    try:
        response = httpx.request(
            probe.method,
            f"{API_URL}{probe.path}",
            headers={"Authorization": f"Bearer {token}"},
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
