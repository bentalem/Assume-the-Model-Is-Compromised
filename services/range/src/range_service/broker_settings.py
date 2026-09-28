"""The delegation broker's switches, for challenges 1.5, 1.7 and 1.8.

Three booleans in one file on the `broker_settings` volume, which the broker reads on every request.
Each armed value is a configuration a real deployment might ship: forward the user's token "so it
just works", auto-approve whatever scope an agent asks for, let a re-exchange recompute scope from
the new agent's ceiling. The Range writes them; the broker decides what they mean, and it never
mints refunds:approve or a scope that is not in the table whatever this file says.

The write is atomic — a temporary file renamed over the real one — so the broker never reads half a
file. It would treat half a file as malformed and fall back to every switch secure, which is safe,
but a probe that read `armed` while the broker enforced `secure` would be the one thing this
service must never report.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from . import probe

logger = logging.getLogger("supportpilot.range.broker_settings")

SETTINGS = Path(os.environ.get("BROKER_SETTINGS_FILE", "/broker-settings/settings.json"))
NAMES = ("broker.passthrough", "ceiling.user_only", "chain.widen")


class BrokerSettingsError(Exception):
    """Raised rather than returning a value nobody checks."""


def _read() -> dict[str, bool]:
    try:
        raw = json.loads(SETTINGS.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {name: False for name in NAMES}
    except (OSError, ValueError) as exc:
        raise BrokerSettingsError(f"settings unreadable: {type(exc).__name__}") from exc
    if not isinstance(raw, dict):
        raise BrokerSettingsError("settings are not an object")
    # The broker's own rule: armed only by the literal `true`.
    return {name: raw.get(name) is True for name in NAMES}


def set_switch(name: str, armed: bool) -> None:
    if name not in NAMES:
        raise BrokerSettingsError(f"unknown switch {name!r}")
    if not SETTINGS.parent.is_dir():
        raise BrokerSettingsError(f"{SETTINGS.parent} is not mounted; the settings volume is missing")
    try:
        current = _read()
    except BrokerSettingsError:
        # A file nobody can parse is replaced rather than merged with.
        current = {n: False for n in NAMES}
    current[name] = armed
    temporary = SETTINGS.with_suffix(".tmp")
    temporary.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    temporary.replace(SETTINGS)
    logger.warning("broker switch %s set to %s", name, "armed" if armed else "secure")


def state(name: str) -> str:
    """armed, correct, absent or unknown — read from the file and, when it matters, the broker.

    Armed is reported whatever the broker's state: the file is the configuration, and a broker that
    starts later enforces it. So reset restores an armed switch even with the broker down, rather
    than leaving it to surprise the next person to bring the profile up. A secure switch is `absent`
    while the broker is not running, because there is then nothing to be correct about.
    """
    try:
        armed = _read()[name]
    except BrokerSettingsError:
        return "unknown"
    if armed:
        return "armed"
    return "correct" if probe.broker_running() else "absent"


def rows() -> list[dict[str, str]]:
    """The switches as the broker would read them, for the console."""
    try:
        values = _read()
    except BrokerSettingsError as exc:
        return [{"switch": name, "value": f"unreadable: {exc}"} for name in NAMES]
    running = probe.broker_running()
    return [
        {"switch": name, "value": "armed" if values[name] else "secure",
         "broker": "running" if running else "not running"}
        for name in NAMES
    ]
