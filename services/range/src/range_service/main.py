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
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from . import db, registry, render
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
        return

    # Say so if the lab is already broken.
    #
    # This exists because it happened: a session left two controls armed, nothing said anything, and
    # the next thing to notice was the migration job refusing to run its smoke tests half an hour
    # later. A service whose whole job is arming controls should be the first to report that it left
    # some armed, not the last.
    try:
        armed = [mid for mid, value in registry.state().items() if value != registry.CORRECT]
    except Exception:  # noqa: BLE001
        logger.exception("could not probe the environment on startup")
        return

    if armed:
        logger.warning(
            "THE LAB IS ARMED on startup: %s — every measurement taken against it is of a broken "
            "system. Reset from any challenge page to restore it.",
            ", ".join(armed),
        )
    else:
        logger.info("environment correct: all %d control(s) at their designed setting", len(registry.MUTATIONS))


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


@app.get("/registry", include_in_schema=False)
def registry_listing() -> JSONResponse:
    """Every mutation and observation the service holds, with each mutation's live probe.

    This exists for `scripts/range_suite.py`, and it exists because of a hard requirement: no
    mutation without a proven inverse. The suite used to round-trip two hardcoded ids, which meant
    every mutation added afterwards was untested by default — the opposite of what that rule asks
    for. It now reads this and round-trips whatever it finds.

    It is a read of the service's own vocabulary, not of the lab. Nothing here can change anything.
    """
    # One probe sweep, not one per mutation. The obvious comprehension re-probes the whole registry
    # for every row, which for the container mutation means an HTTP round trip per row.
    state = registry.state()
    return JSONResponse(
        {
            "mutations": [
                {
                    "id": mutation.id,
                    "summary": mutation.summary,
                    "touches": list(mutation.touches),
                    "state": state.get(mutation.id, registry.UNKNOWN),
                }
                for mutation in registry.MUTATIONS.values()
            ],
            "observations": [
                {"id": obs.id, "summary": obs.summary, "row_cap": obs.row_cap}
                for obs in registry.OBSERVATIONS.values()
            ],
        }
    )


@app.get("/robots.txt", include_in_schema=False)
def robots() -> PlainTextResponse:
    return PlainTextResponse("User-agent: *\nDisallow: /\n")


@app.get("/guide", response_class=HTMLResponse, include_in_schema=False)
def guide() -> HTMLResponse:
    """How to use the range. Linked from the catalogue, and the first thing to read."""
    return HTMLResponse(render.page("How to use The Range", render.guide(_challenges)))


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> HTMLResponse:
    return HTMLResponse(render.page("Catalogue", render.catalogue(_challenges)))


def _tabs(request: Request) -> tuple[int, int]:
    def tab(name: str) -> int:
        raw = request.query_params.get(name, "0")
        return int(raw) if raw.isdigit() else 0

    return tab("stage-01"), tab("stage-03")


def _render(challenge, request: Request, **kwargs) -> HTMLResponse:
    """Render a challenge with the live environment state, always read from the system."""
    tab_01, tab_03 = _tabs(request)
    try:
        state = registry.state()
    except Exception:  # noqa: BLE001 — an unreadable state is shown as unknown, never as correct
        logger.exception("could not probe environment state")
        state = {mid: registry.UNKNOWN for mid in registry.MUTATIONS}
    return HTMLResponse(render.challenge_page(challenge, tab_01, tab_03, state=state, **kwargs))


@app.get("/c/{challenge_id}", response_class=HTMLResponse, include_in_schema=False)
def challenge(challenge_id: str, request: Request) -> HTMLResponse:
    found = _by_id.get(challenge_id)
    if found is None:
        return HTMLResponse(
            render.not_found(f"No challenge with id {challenge_id!r} is loaded."), status_code=404
        )
    return _render(found, request)


# --------------------------------------------------------------------------------------------------
# The console.
#
# Every one of these takes an identifier and nothing else, and the identifier is checked twice:
# against the ids this challenge declares, and against the registry. A mutation id that is real but
# not part of this challenge is refused — the console is not a general remote control that happens
# to be rendered next to a lesson.
# --------------------------------------------------------------------------------------------------

def _declared_mutations(challenge) -> set[str]:
    return {control.mutation for control in challenge.controls}


def _declared_observations(challenge) -> set[str]:
    return {obs.observation for obs in challenge.observations}


@app.post("/c/{challenge_id}/{action}", response_class=HTMLResponse, include_in_schema=False)
async def console(challenge_id: str, action: str, request: Request) -> HTMLResponse:
    found = _by_id.get(challenge_id)
    if found is None:
        return HTMLResponse(render.not_found(f"No challenge {challenge_id!r}."), status_code=404)
    if action not in {"arm", "restore", "observe", "reset", "flag"}:
        return HTMLResponse(render.not_found(f"Unknown action {action!r}."), status_code=404)

    form = await request.form()
    request_id = f"range-{uuid.uuid4()}"

    try:
        if action in {"arm", "restore"}:
            mutation_id = str(form.get("mutation", ""))
            if mutation_id not in _declared_mutations(found):
                return HTMLResponse(
                    render.not_found(f"{mutation_id!r} is not a control of this challenge."),
                    status_code=400,
                )
            fn = registry.apply if action == "arm" else registry.restore
            probe = fn(mutation_id, request_id)
            return _render(found, request, ran=f"{action} {mutation_id} → {probe}")

        if action == "observe":
            observation_id = str(form.get("observation", ""))
            if observation_id not in _declared_observations(found):
                return HTMLResponse(
                    render.not_found(f"{observation_id!r} is not an observation of this challenge."),
                    status_code=400,
                )
            columns, rows = registry.observe(observation_id)
            return _render(
                found, request,
                result=render._result_table(columns, rows),
                ran=f"observation {observation_id}",
            )

        if action == "reset":
            changed = registry.reset(request_id)
            detail = ", ".join(changed) if changed else "nothing was armed"
            return _render(found, request, ran=f"reset → restored: {detail}")

        # action == "flag"
        answer = str(form.get("answer", "")).strip()
        ok, note = _check_flag(found, answer)
        return _render(found, request, flag_note=note, flag_ok=ok)

    except Exception as exc:  # noqa: BLE001 — the learner is told, and the log carries the trace
        logger.exception("console action failed: %s %s", action, challenge_id)
        return _render(found, request, ran=f"{action} failed: {type(exc).__name__}")


def _check_flag(challenge, answer: str) -> tuple[bool, str]:
    """Check an answer against the database rather than against a literal in a content file.

    A `value` flag names an observation and a column; the answer has to match a value that
    observation currently returns. That is what makes the flag unobtainable while the control holds:
    when the environment is correct, the observation simply does not produce it.
    """
    flag = challenge.flag
    if flag is None:
        return False, "This challenge has no flag."
    if not answer:
        return False, "Enter a value."

    if flag.kind == "value":
        values = registry.observation_values(flag.observation, flag.field)
        normalised = {value.rstrip("0").rstrip(".") if "." in value else value for value in values}
        candidate = answer.rstrip("0").rstrip(".") if "." in answer else answer
        if candidate in normalised or answer in values:
            # Only a challenge that arms something can claim the answer was previously unreachable.
            # Saying it on a read-only challenge would be the service telling the learner something
            # untrue about its own controls, in a course about exactly that.
            if challenge.controls:
                return True, "Correct — and note that you could not have read this a minute ago."
            return True, "Correct."
        return False, "Not a value this observation returns right now."

    if flag.kind == "reason":
        return (
            (True, "Correct.") if answer == flag.reason_code
            else (False, "Not the reason code recorded for that decision.")
        )

    # written: scored against a rubric of required points, not a string match.
    hits = [point for point in flag.rubric if point.lower() in answer.lower()]
    if len(hits) >= max(1, len(flag.rubric) - 1):
        return True, f"Covers {len(hits)} of {len(flag.rubric)} required points."
    return False, f"Covers {len(hits)} of {len(flag.rubric)} required points — say more."


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
