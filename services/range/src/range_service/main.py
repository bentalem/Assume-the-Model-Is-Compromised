"""The Range.

A web application that arms the lab's controls into broken states, lets a learner see the
consequence, shows the lab's own source for why, and puts it back.

One rule shapes every decision in this service: **the learner never opens a terminal.** If a
challenge needs a command, the Range runs it.

A second rule shapes the service itself. To arm a challenge the Range must be able to drop FORCE on
a table, change how the API connects, stop a container. That is more authority than anything else in
this repository holds, and a service that can do all of it is exactly the control-plane violation
the lab spends eight tracks teaching people to find. So it is bounded the way the lab would demand
of anything else:

  * it refuses to start anywhere but `local`, and that refusal is a test;
  * it is not in the action document, not on the `app` network, and holds no route the model can
    name;
  * its database role owns nothing and can read no table directly;
  * everything it does is written to the same audit trail the learner will later investigate.

The Range is the first thing a graduate of this course should be able to criticise.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from . import db, render
from .content import Challenge, load_all

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("supportpilot.range")

CONTENT_ROOT = Path(os.environ.get("RANGE_CONTENT_DIR", "/app/content"))


class EnvironmentRefused(RuntimeError):
    """Raised when the Range is asked to run outside a local lab."""


def assert_local(environment: str | None = None) -> str:
    """The Range runs in a local lab or it does not run.

    This is not a formality. Every other guard in this service — the fixed registry, the absent
    grants, the audit trail — limits what the Range can do to a system it is *supposed* to break.
    This one is what stops it being pointed at a system it is not.
    """
    value = environment if environment is not None else os.environ.get("SUPPORTPILOT_ENV", "")
    if value != "local":
        raise EnvironmentRefused(
            f"SUPPORTPILOT_ENV is {value!r}; the Range starts only when it is 'local'. "
            "This service arms controls into broken states and must never be reachable from an "
            "environment that matters."
        )
    return value


app = FastAPI(
    title="SupportPilot Range",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

_challenges: list[Challenge] = []
_by_id: dict[str, Challenge] = {}


@app.on_event("startup")
def startup() -> None:
    assert_local()
    global _challenges, _by_id
    _challenges = load_all(CONTENT_ROOT)
    _by_id = {challenge.id: challenge for challenge in _challenges}

    ok, detail = db.healthy()
    if ok:
        logger.info("database reachable as sp_range_role: %s", detail)
    else:
        # Not fatal. The catalogue and every Stage 01 render without a database, and a learner
        # reading the material should not be stopped by a service that is still coming up.
        logger.error("database not reachable: %s", detail)


@app.get("/healthz", include_in_schema=False)
def healthz() -> JSONResponse:
    ok, detail = db.healthy()
    return JSONResponse(
        {
            "status": "ok" if ok else "degraded",
            "environment": os.environ.get("SUPPORTPILOT_ENV", ""),
            "challenges": len(_challenges),
            "database": detail,
        },
        status_code=200 if ok else 503,
    )


@app.get("/robots.txt", include_in_schema=False)
def robots() -> PlainTextResponse:
    return PlainTextResponse("User-agent: *\nDisallow: /\n")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> HTMLResponse:
    return HTMLResponse(render.page("Catalogue", render.catalogue(_challenges)))


@app.get("/c/{challenge_id}", response_class=HTMLResponse, include_in_schema=False)
def challenge(challenge_id: str, request: Request) -> HTMLResponse:
    found = _by_id.get(challenge_id)
    if found is None:
        return HTMLResponse(
            render.not_found(f"No challenge with id {challenge_id!r} is loaded."), status_code=404
        )

    def tab(name: str) -> int:
        raw = request.query_params.get(name, "0")
        return int(raw) if raw.isdigit() else 0

    return HTMLResponse(render.challenge_page(found, tab("stage-01"), tab("stage-03")))


def run() -> None:
    import uvicorn

    try:
        assert_local()
    except EnvironmentRefused as exc:
        # Exit before binding a port. A refusal that happens after the service is listening is not
        # a refusal.
        print(f"range: {exc}", file=sys.stderr)
        raise SystemExit(78)  # EX_CONFIG

    uvicorn.run(
        app,
        host="0.0.0.0",  # noqa: S104 — published only on 127.0.0.1 by compose
        port=int(os.environ.get("PORT", "8095")),
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )
