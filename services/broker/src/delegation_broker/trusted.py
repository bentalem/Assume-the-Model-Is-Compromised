"""The trusted configuration the broker decides from: scopes, profiles, and the lab's settings.

Everything that sets a limit comes from here, and nothing here comes from a request:

* **Scopes** — `policy/supportpilot/scopes.json`, the same file OPA loads, mounted read-only. One
  table says which scope each API action needs, for the policy and for the broker alike. Two copies
  would drift; one cannot.
* **Profiles** — `infrastructure/local/broker/profiles.json`. How an agent is registered: its name
  and its ceiling, set by an administrator and never by the model. The broker refuses to start if a
  profile names a scope that does not exist or one that may never be delegated.
* **Settings** — the lab's three switches, read from the Range's settings volume on every request so
  arming takes effect without a restart. Missing, unreadable or malformed means every switch at its
  secure value. A setting is armed only by the literal JSON `true`: `"true"`, `1` and `"yes"` are
  not, because a lenient parser is how a typo becomes an armed control.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("supportpilot.broker.trusted")

PROFILE_NAME = re.compile(r"^[a-z][a-z0-9-]{0,62}$")

SETTING_NAMES = ("broker.passthrough", "ceiling.user_only", "chain.widen")


class ConfigurationRefused(RuntimeError):
    """The broker will not start on configuration that could mint something it must not."""


@dataclass(frozen=True)
class ScopeTable:
    actions: dict[str, str]
    never_delegable: frozenset[str]

    @property
    def known(self) -> frozenset[str]:
        return frozenset(self.actions.values())

    @property
    def delegable(self) -> frozenset[str]:
        return self.known - self.never_delegable

    def for_action(self, action: str) -> str | None:
        return self.actions.get(action)


def load_scopes(path: Path) -> ScopeTable:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))["scopes"]
        actions = {str(k): str(v) for k, v in raw["actions"].items()}
        never = frozenset(str(s) for s in raw["never_delegable"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ConfigurationRefused(f"scope table unreadable at {path}: {type(exc).__name__}") from exc
    if not actions:
        raise ConfigurationRefused("the scope table maps no action")
    return ScopeTable(actions=actions, never_delegable=never)


@dataclass(frozen=True)
class Profile:
    name: str
    ceiling: frozenset[str]
    description: str
    # The credential the agent platform authenticates with. Never logged, never returned, and kept
    # out of repr so a traceback or a debug print of a profile cannot carry it.
    _secret: str = field(repr=False)

    def authenticates(self, presented: str) -> bool:
        return bool(presented) and secrets.compare_digest(presented, self._secret)


def load_profiles(path: Path, secrets_dir: Path, scopes: ScopeTable) -> dict[str, Profile]:
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))["profiles"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ConfigurationRefused(f"profiles unreadable at {path}: {type(exc).__name__}") from exc

    profiles: dict[str, Profile] = {}
    for row in rows:
        name = str(row.get("name", ""))
        if not PROFILE_NAME.match(name) or name in profiles:
            raise ConfigurationRefused(f"profile name {name!r} is malformed or repeated")
        ceiling = frozenset(str(s) for s in row.get("ceiling", []))
        unknown = ceiling - scopes.known
        if unknown:
            raise ConfigurationRefused(f"profile {name} names unknown scopes {sorted(unknown)}")
        forbidden = ceiling & scopes.never_delegable
        if forbidden:
            # The rule is also enforced by the policy, at the resource server. Refusing to start
            # here as well means a mistake in this file is found at deploy, not in production.
            raise ConfigurationRefused(
                f"profile {name} includes {sorted(forbidden)}, which may never be delegated"
            )
        secret_file = secrets_dir / f"broker_profile_{name.replace('-', '_')}"
        try:
            secret = secret_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigurationRefused(f"credential for profile {name} is not mounted") from exc
        if not secret:
            raise ConfigurationRefused(f"credential for profile {name} is empty")
        profiles[name] = Profile(
            name=name, ceiling=ceiling, description=str(row.get("description", "")), _secret=secret
        )
    if not profiles:
        raise ConfigurationRefused("no profile is registered")
    return profiles


def read_settings(path: Path) -> dict[str, bool]:
    """The lab's switches, at their secure values unless the file says exactly otherwise."""
    secure = {name: False for name in SETTING_NAMES}
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return secure
    except OSError:
        logger.warning("broker settings unreadable; every setting at its secure value")
        return secure
    try:
        raw = json.loads(text)
    except ValueError:
        logger.warning("broker settings malformed; every setting at its secure value")
        return secure
    if not isinstance(raw, dict):
        logger.warning("broker settings are not an object; every setting at its secure value")
        return secure
    return {name: raw.get(name) is True for name in SETTING_NAMES}
