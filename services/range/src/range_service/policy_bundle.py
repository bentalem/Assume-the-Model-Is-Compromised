"""Arming a permissive authorization policy, for challenge 3.3.

3.3 is the challenge about what "two layers" actually means. Building it needs OPA to load a
different bundle, and how that is done matters more than usual.

**The wrong policy is derived, never stored.** There is no permissive `.rego` file in this
repository or in this image. Arming reads the real policy from the read-only repository mount,
removes one named condition from it, and writes the result to OPA's bundle volume. That is a
deliberate choice against the obvious alternative of shipping a second, hand-written bundle: a
stored copy drifts the first time somebody edits the real policy, and the challenge would then arm
a policy the lab no longer runs while telling the learner it is theirs with one control removed.

The transform asserts that the text it expects is present and that the output differs from the
input. If the policy is edited in a way that moves them, arming fails loudly instead of silently
arming nothing — the failure mode that made a mutation a no-op earlier in this project, found only
because a display name had changed.

**The bundle is a volume, not the working tree.** See the `opa_bundle` volume in `compose.yaml`.
A mutation that wrote to `./policy/supportpilot` could leave a crashed container's permissive
authorization policy checked out in a git clone, and "no mutation without a proven inverse" stops
being true the moment the inverse depends on the container still being alive.

**Two variants, and the difference between them is the whole challenge.** `tenant` removes the
tenant membership check from `order.read`. `role` removes the role check from the same action. They
are not two ways of saying the same thing:

  * The API loads the trusted resource *before* it asks the policy anything — see `pipeline.py`,
    where `resource is None` denies `resource_not_visible` and returns. A cross-tenant read finds no
    resource, so OPA is never consulted, so arming `tenant` changes nothing observable, including in
    the audit trail. The database was already the control and the policy was redundant for it.
  * Nothing except the policy checks roles. Row-level security can express "this row belongs to
    another tenant"; it cannot express "this role may not read orders". So arming `role` returns
    data to a user who should not have it, and there is no second layer underneath.

That asymmetry is a property of this architecture rather than a scenario written for the lesson, and
`range_suite.py` asserts both outcomes rather than repeating these two paragraphs.
"""

from __future__ import annotations

import logging
from pathlib import Path

from . import containers

logger = logging.getLogger("supportpilot.range.policy_bundle")

# The policy as the repository holds it: read-only, and the restore path's source of truth.
SOURCE = Path("/repo/policy/supportpilot/authz.rego")
# The bundle OPA loads.
DEPLOYED = Path("/opa-bundle/authz.rego")
# The container that loads it. Must match registry.OPA_CONTAINER.
OPA_CONTAINER = "supportpilot-opa"

# The three arms of order.read, written out in full rather than matched by regex: a regex that
# silently matched nothing would arm a policy identical to the real one and report success.
_ALLOW_ARM = (
    'decision := allow_with("same_organization_and_allowed_role", '
    '{"allowed_fields": order_fields}) if {\n'
    '\tinput.action == "order.read"\n'
    "\tin_tenant\n"
    "\tany_role(read_roles)\n"
    "}"
)
_DENY_TENANT = (
    'decision := deny("not_a_member_of_resource_organization") if {\n'
    '\tinput.action == "order.read"\n'
    "\tnot in_tenant\n"
    "}"
)
_DENY_ROLE = (
    'decision := deny("role_not_permitted_for_action") if {\n'
    '\tinput.action == "order.read"\n'
    "\tin_tenant\n"
    "\tnot any_role(read_roles)\n"
    "}"
)

# An arm that is true for every order.read, so it collides with whichever real arm also matches.
# Rego refuses to produce two different values for a complete rule, so OPA answers 500 at eval time
# rather than at load time — which is the failure mode that reaches the API as a bad status.
_CONFLICT_RULE = (
    "\n\n"
    'decision := deny("range_conflict_probe") if {\n'
    '\tinput.action == "order.read"\n'
    "}\n"
)

# Moving the package makes `data.supportpilot.authz.decision` undefined. OPA answers 200 with no
# "result" key at all, which the client treats as malformed rather than as a permissive silence.
_REAL_PACKAGE = "package supportpilot.authz\n"
_MOVED_PACKAGE = "package supportpilot.authz_moved\n"

# variant -> (the condition removed from the allow arm, the deny arm that goes with it)
VARIANTS = {
    "tenant": ("\tin_tenant\n", _DENY_TENANT),
    "role": ("\tany_role(read_roles)\n", _DENY_ROLE),
}


class PolicyBundleError(Exception):
    """Raised rather than returning a value nobody checks."""


def _source_text() -> str:
    if not SOURCE.is_file():
        raise PolicyBundleError(f"{SOURCE} is not mounted; the Range cannot read the real policy")
    return SOURCE.read_text(encoding="utf-8")


BROKEN = ("conflict", "undefined")


def _broken_text(variant: str) -> str:
    """A bundle that loads but cannot answer, for challenge 3.4."""
    source = _source_text()
    if variant == "conflict":
        return source + _CONFLICT_RULE
    if _REAL_PACKAGE not in source:
        raise PolicyBundleError("the package declaration is not where this transform expects it")
    return source.replace(_REAL_PACKAGE, _MOVED_PACKAGE, 1)


def permissive_text(variant: str) -> str:
    """The real policy with one named condition removed, or broken in one named way."""
    if variant in BROKEN:
        return _broken_text(variant)
    if variant not in VARIANTS:
        raise PolicyBundleError(f"unknown variant {variant!r}")
    condition, deny_arm = VARIANTS[variant]
    source = _source_text()

    if _ALLOW_ARM not in source:
        raise PolicyBundleError(
            "the order.read allow arm is not where this transform expects it; the policy has been "
            "edited and this mutation must be updated rather than arming something else"
        )
    # Checked against the arm itself, but removed together with the blank line that follows it.
    # Those are different strings: if the arm is ever followed by one newline instead of two, the
    # check passes and the removal silently does nothing, leaving a policy with the allow condition
    # gone and the deny arm intact — armed according to the probe, and refusing exactly as before.
    removable = deny_arm + "\n\n"
    if removable not in source:
        raise PolicyBundleError(
            f"the {variant} deny arm for order.read is not where this transform expects it, or is "
            "no longer followed by a blank line; the policy has been edited and this mutation must "
            "be updated rather than arming half of itself"
        )

    out = source.replace(_ALLOW_ARM, _ALLOW_ARM.replace(condition, ""), 1)
    out = out.replace(removable, "", 1)

    if out == source:
        raise PolicyBundleError("the transform changed nothing")
    return out


def _write(text: str) -> None:
    if not DEPLOYED.parent.is_dir():
        raise PolicyBundleError(f"{DEPLOYED.parent} is not mounted; the bundle volume is missing")
    DEPLOYED.write_text(text, encoding="utf-8", newline="\n")


def arm(variant: str) -> None:
    """Install the altered policy. The caller restarts OPA."""
    _write(permissive_text(variant))
    if variant in BROKEN:
        logger.warning("armed: OPA's bundle has been made %s and can no longer answer", variant)
    else:
        logger.warning("armed: the %s check has been removed from order.read in OPA's bundle", variant)


def restore() -> None:
    """Put the real policy back, copied from the read-only repository mount."""
    _write(_source_text())
    logger.info("restored: OPA's bundle is the repository's policy again")


def _opa_has_loaded_the_bundle() -> bool:
    """Whether OPA started after the bundle was last written.

    This is the difference between reading the file and reading the system. OPA loads its bundle
    once, at startup, and does not watch the directory — so the file on disk and the policy being
    enforced are two things that have to agree, not one thing.

    They come apart in two ordinary ways. `restore()` writes the file and then restarts OPA; if the
    restart fails, the file is correct and the engine is still armed. And `docker compose up -d`
    re-runs `opa-bundle-init`, which copies the repository policy over the volume while a running
    OPA is left alone, because compose sees no reason to recreate it.

    Without this check `state()` reported `correct` in both cases — the one thing the probe must
    never do. Found by a review, then reproduced: armed the role check, wrote the real policy back
    without restarting, and watched the probe say `correct` while fiona still read the order.

    An unreachable runtime answers `False`. Not knowing is not the same as being correct.
    """
    try:
        started = containers.started_at(OPA_CONTAINER)
    except containers.ContainerError:
        logger.warning("cannot tell whether OPA has loaded the bundle; reporting unknown")
        return False
    return started >= DEPLOYED.stat().st_mtime


def state(variant: str) -> str:
    """Whether OPA is enforcing the real policy, this variant of it, or something unrecognised.

    Byte comparison against both known texts, and then the question of whether OPA has actually
    read what it is being compared against. Anything else is reported as unknown rather than
    guessed at — a probe that answered `correct` for a policy nobody recognises, or for a file the
    engine never loaded, would be the one thing in this service that must never happen. Both
    variants write the same file, so arming one while the other is armed leaves the first reading
    `unknown`, which is the intended answer.
    """
    if not DEPLOYED.is_file():
        return "unknown"
    deployed = DEPLOYED.read_text(encoding="utf-8")
    if deployed == _source_text():
        answer = "correct"
    elif deployed == permissive_text(variant):
        answer = "armed"
    else:
        return "unknown"
    return answer if _opa_has_loaded_the_bundle() else "unknown"
