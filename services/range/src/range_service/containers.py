"""Stopping and starting a container, through the proxy.

The Range does not have the Docker socket, and this module is why that matters. A service holding
that socket is root on the host: it can start a privileged container, mount the host filesystem, and
read every secret in the repository. That is not a smaller version of the authority the Range needs
— it is unbounded authority handed to the one service whose job is breaking things.

So the Range talks to an HAProxy configuration that permits three verbs on three container names and
refuses everything else, including `exec`. The worst a compromised Range can do through this path is
restart three containers in a local lab, which is also the best it can do.

`name` here is always a literal from `registry.py`. Nothing derived from a request reaches it — and
the proxy would refuse it anyway, which is the point of having both.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime

logger = logging.getLogger("supportpilot.range.containers")

PROXY = os.environ.get("DOCKER_PROXY_URL", "http://docker-proxy:2375")


class ContainerError(Exception):
    """The proxy refused, or the container did not reach the state we asked for."""


def _request(method: str, path: str, timeout: int = 30) -> tuple[int, bytes]:
    request = urllib.request.Request(f"{PROXY}{path}", method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except Exception as exc:  # noqa: BLE001
        raise ContainerError(f"proxy unreachable: {type(exc).__name__}") from exc


def state(name: str) -> str:
    """`running`, `exited`, or whatever Docker says. Never remembered — always asked."""
    status, body = _request("GET", f"/containers/{name}/json")
    if status != 200:
        raise ContainerError(f"inspect {name}: HTTP {status}")
    try:
        return json.loads(body)["State"]["Status"]
    except (json.JSONDecodeError, KeyError) as exc:
        raise ContainerError(f"inspect {name}: unreadable response") from exc


def _wait_for(name: str, wanted: str, seconds: int = 45) -> None:
    """Wait until the container reaches a state, or say plainly that it did not.

    This exists because of what a reset means. `restore` returning before the container is back is a
    reset that reports success while the lab is still broken — the precise failure the whole registry
    is built to prevent, reintroduced by an asynchronous operation.
    """
    deadline = time.time() + seconds
    while time.time() < deadline:
        if state(name) == wanted:
            return
        time.sleep(1)
    raise ContainerError(f"{name} did not reach {wanted!r} within {seconds}s")


def stop(name: str) -> None:
    status, body = _request("POST", f"/containers/{name}/stop", timeout=60)
    # 304 is "already stopped", which is success for our purposes.
    if status not in (204, 304):
        raise ContainerError(f"stop {name}: HTTP {status} {body[:120]!r}")
    _wait_for(name, "exited")


def start(name: str) -> None:
    status, body = _request("POST", f"/containers/{name}/start", timeout=60)
    if status not in (204, 304):
        raise ContainerError(f"start {name}: HTTP {status} {body[:120]!r}")
    _wait_for(name, "running")


def started_at(name: str) -> float:
    """When this container last started, as epoch seconds, read from the runtime.

    Used to answer a question a file cannot: has this process read the file that is on disk now?
    A bundle that OPA has not loaded says nothing about what OPA is enforcing.
    """
    status, body = _request("GET", f"/containers/{name}/json")
    if status != 200:
        raise ContainerError(f"inspect {name}: HTTP {status}")
    try:
        raw = json.loads(body)["State"]["StartedAt"]
    except (json.JSONDecodeError, KeyError) as exc:
        raise ContainerError(f"inspect {name}: unreadable response") from exc
    return _epoch(raw)


def _epoch(value: str) -> float:
    """Docker reports RFC 3339 with nanoseconds; datetime accepts at most six fractional digits."""
    text = value.replace("Z", "+00:00")
    if "." in text:
        head, _, rest = text.partition(".")
        digits = ""
        while rest and rest[0].isdigit():
            digits, rest = digits + rest[0], rest[1:]
        text = head + "." + digits[:6] + rest
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError as exc:
        raise ContainerError(f"unreadable container timestamp {value!r}") from exc
