"""Asking the probe service for one named request.

The Range cannot reach the API. It can ask `probe` for one of a fixed list of requests, by id, over
the `control` network and with a shared secret. That is a smaller thing than a route to the API, and
the difference is the whole point of the probe service.

Nothing in this module composes a request. `run()` takes an id that came from a challenge's declared
observation list, and the probe service refuses any id that is not in its own registry — so the
vocabulary is checked twice, in two services, neither of which can extend it.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger("supportpilot.range.probe")

PROBE_URL = os.environ.get("PROBE_URL", "http://probe:8096")


def _secret() -> str:
    path = os.environ.get("PROBE_SHARED_SECRET_FILE", "/run/secrets/probe_shared_secret")
    with open(path, encoding="utf-8") as handle:
        return handle.read().strip()


def run(probe_id: str, kind: str = "probe") -> list[dict[str, Any]]:
    """Run one registered probe and return a single row describing what happened.

    A failure is returned as a row rather than raised. A learner looking at a result panel needs to
    see that the probe service is unreachable; an exception would render as a generic error and
    leave them guessing which half of the system was broken.
    """
    request = urllib.request.Request(
        f"{PROBE_URL}/{kind}/{probe_id}",
        method="POST",
        headers={"X-Range-Token": _secret()},
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        return [{"request": probe_id, "status": str(exc.code), "error_code": "probe_refused",
                 "fields": "", "intent": "the probe service refused this id"}]
    except Exception as exc:  # noqa: BLE001
        logger.exception("probe call failed: %s", probe_id)
        return [{"request": probe_id, "status": "-", "error_code": type(exc).__name__,
                 "fields": "", "intent": "the probe service could not be reached"}]

    return [
        {
            "request": payload.get("request", probe_id),
            "as_user": payload.get("user", ""),
            "status": str(payload.get("status", "")),
            "error_code": payload.get("error_code") or "-",
            "fields": ", ".join(payload.get("fields", [])) or "-",
            "intent": payload.get("intent", ""),
        }
    ]


def enumerate_directory(enumeration_id: str) -> list[dict[str, Any]]:
    """Run a registered enumeration and report what the sequence of calls added up to.

    For challenge 4.3. The probe service returns counts, never records — which is the same rule
    every other probe follows and matters more here, because records are the thing the challenge is
    about reaching.
    """
    request = urllib.request.Request(
        f"{PROBE_URL}/enumerate/{enumeration_id}",
        method="POST",
        headers={"X-Range-Token": _secret()},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        return [{"calls": "-", "distinct_records": "-", "every_call_allowed": "-",
                 "more_pages_remaining": "-", "intent": f"the probe service refused: {exc.code}"}]
    except Exception as exc:  # noqa: BLE001
        logger.exception("enumeration call failed: %s", enumeration_id)
        return [{"calls": "-", "distinct_records": "-", "every_call_allowed": "-",
                 "more_pages_remaining": "-", "intent": f"unreachable: {type(exc).__name__}"}]

    return [
        {
            "calls": str(payload.get("calls", "-")),
            "distinct_records": str(payload.get("distinct_records", "-")),
            "every_call_allowed": "yes" if payload.get("every_call_allowed") else "no",
            "more_pages_remaining": "yes" if payload.get("more_pages_remaining") else "no",
            "intent": payload.get("intent", ""),
        }
    ]


def run_scenario(scenario_id: str) -> list[dict[str, Any]]:
    """Run one registered track 9 scenario and return a row per step.

    Status, error code and field names per step — the same thin shape as every probe. What the steps
    left in memory-db is read afterwards by an observation, never carried back here.
    """
    request = urllib.request.Request(
        f"{PROBE_URL}/scenario/{scenario_id}",
        method="POST",
        headers={"X-Range-Token": _secret()},
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        return [{"step": "-", "as_user": "", "request": scenario_id, "status": str(exc.code),
                 "error_code": "probe_refused", "fields": "-"}]
    except Exception as exc:  # noqa: BLE001
        logger.exception("scenario call failed: %s", scenario_id)
        return [{"step": "-", "as_user": "", "request": scenario_id, "status": "-",
                 "error_code": type(exc).__name__, "fields": "-"}]

    return [
        {
            "step": str(step.get("step", "")),
            "as_user": f"{payload.get('user', '')} ({payload.get('acts_as', '')})",
            "request": step.get("request", ""),
            "status": str(step.get("status", "")),
            "error_code": step.get("error_code") or "-",
            "fields": ", ".join(step.get("fields", [])) or "-",
        }
        for step in payload.get("steps", [])
    ]


# --------------------------------------------------------------------------------------------------
# Track 1, 1.5 - 1.8: delegation. The Range cannot reach the broker; the probe can, and it holds the
# profile credentials an agent would. Same rule as every probe: a fixed id, a thin row.
# --------------------------------------------------------------------------------------------------

def _get(path: str, timeout: int = 15) -> dict[str, Any]:
    request = urllib.request.Request(f"{PROBE_URL}{path}", headers={"X-Range-Token": _secret()})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def broker_running() -> bool:
    """Whether the broker answers, asked of the probe. Not knowing is reported as not running."""
    try:
        return _get("/delegation-health").get("broker") == "running"
    except Exception:  # noqa: BLE001
        logger.warning("could not ask the probe whether the broker is running")
        return False


def run_delegation(delegation_id: str) -> list[dict[str, Any]]:
    """Run one registered delegation probe and return its single row."""
    request = urllib.request.Request(
        f"{PROBE_URL}/delegation/{delegation_id}",
        method="POST",
        headers={"X-Range-Token": _secret()},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            payload = json.load(exc)
        except Exception:  # noqa: BLE001
            payload = {"status": exc.code, "error_code": "probe_refused"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("delegation call failed: %s", delegation_id)
        return [{"request": delegation_id, "token": "", "status": "-",
                 "error_code": type(exc).__name__, "revealed": "",
                 "intent": "the probe service could not be reached"}]
    return [
        {
            "request": payload.get("request", delegation_id),
            "token": payload.get("token", ""),
            "status": str(payload.get("status", "")),
            "error_code": payload.get("error_code") or "-",
            "revealed": payload.get("revealed", ""),
            "intent": payload.get("intent", ""),
        }
    ]


def last_minted() -> list[dict[str, Any]]:
    """The claims of the last token the probe obtained — names and values, never the token."""
    try:
        claims = _get("/delegation-claims").get("claims", {})
    except Exception as exc:  # noqa: BLE001
        return [{"claim": "-", "value": f"unreachable: {type(exc).__name__}"}]
    if not claims:
        return [{"claim": "-", "value": "no token obtained yet: run a delegation observation first"}]
    order = ("via", "iss", "sub", "act", "aud", "scope", "expires_in")
    return [{"claim": name, "value": claims.get(name, "")} for name in order]
