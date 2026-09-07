"""Refund provider adapters.

Two implementations behind one contract, so the same tests run against both (`P4-19`): a fake for
local work, and a sandbox adapter for a real provider once one is chosen (OD-02).

Every adapter obeys the same rules:

* **Destination allowlist.** An adapter may only reach hosts it was configured with. A refund that
  could be sent anywhere is an exfiltration channel.
* **Idempotency key on every call.** The provider is asked to deduplicate too, so a network retry
  cannot create a second effect even before our own unique constraint sees it.
* **Ambiguity is a distinct outcome.** A timeout is not a failure. Reporting it as one would invite
  a retry of an operation that may already have moved money.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class Outcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    #: The provider may or may not have applied the effect. Never retried blindly.
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class RefundResult:
    outcome: Outcome
    provider_reference: str | None
    detail: str | None = None


class RefundAdapter(Protocol):
    name: str

    def execute(self, *, idempotency_key: str, payload: dict[str, Any]) -> RefundResult:
        """Apply the refund, at most once for a given idempotency key."""

    def lookup(self, *, idempotency_key: str) -> RefundResult | None:
        """Ask the provider what happened to this key.

        This is what makes an ambiguous timeout recoverable: before retrying, the worker asks the
        provider whether the first attempt landed.
        """


class FakeRefundAdapter:
    """In-memory adapter for local work and contract tests.

    Deliberately more than a stub: it enforces the same idempotency the real provider must, so a
    bug in the worker's retry logic fails here rather than in a sandbox.
    """

    name = "fake"

    def __init__(self) -> None:
        self._applied: dict[str, RefundResult] = {}
        #: Test hooks. Set to make the next call fail or hang ambiguously.
        self.next_outcome: Outcome | None = None

    def execute(self, *, idempotency_key: str, payload: dict[str, Any]) -> RefundResult:
        if idempotency_key in self._applied:
            # The defining property: replaying a key returns the original result and applies
            # nothing new.
            return self._applied[idempotency_key]

        forced = self.next_outcome
        self.next_outcome = None

        if forced is Outcome.FAILED:
            return RefundResult(Outcome.FAILED, None, "forced failure")

        reference = "re_" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:20]

        if forced is Outcome.AMBIGUOUS:
            # The effect *did* land, but the caller never learned that. This is the dangerous case,
            # and reconciliation must find it.
            self._applied[idempotency_key] = RefundResult(Outcome.SUCCEEDED, reference)
            return RefundResult(Outcome.AMBIGUOUS, None, "provider timed out")

        result = RefundResult(Outcome.SUCCEEDED, reference)
        self._applied[idempotency_key] = result
        return result

    def lookup(self, *, idempotency_key: str) -> RefundResult | None:
        return self._applied.get(idempotency_key)


class SandboxRefundAdapter:
    """Adapter for a real provider sandbox.

    Not wired to a provider yet — OD-02 chooses one. The shape is here so that choosing a provider
    is a matter of filling in two methods against the same contract, rather than redesigning the
    worker.
    """

    name = "sandbox"

    def __init__(self, *, base_url: str, allowed_hosts: frozenset[str], timeout_seconds: float = 10.0) -> None:
        from urllib.parse import urlparse

        host = urlparse(base_url).hostname or ""
        if host not in allowed_hosts:
            # Refused at construction, not at call time: an adapter pointed somewhere it should not
            # be must not exist at all.
            raise ValueError(f"destination {host!r} is not in the allowlist")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    def execute(self, *, idempotency_key: str, payload: dict[str, Any]) -> RefundResult:
        raise NotImplementedError(
            "No provider selected yet (OD-02). Phase 4 completes against FakeRefundAdapter; "
            "provider evidence is an open launch-gate condition."
        )

    def lookup(self, *, idempotency_key: str) -> RefundResult | None:
        raise NotImplementedError("No provider selected yet (OD-02).")
