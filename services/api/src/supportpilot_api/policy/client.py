"""OPA client.

The client is as important as the policy. Its whole job is to turn anything other than an explicit,
well-formed `allow: true` into a deny — timeout, connection error, non-200, missing `result`,
`allow` absent or not a boolean true, missing reason, missing policy version, evaluation conflict.

Two prohibitions are structural rather than commented:

* There is no allow cache. `Decision` is constructed per call.
* There is no retry. A denied call is never repeated with modified input.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Reason codes the client itself produces. Policy reasons come from the bundle.
REASON_UNAVAILABLE = "policy_unavailable"
REASON_MALFORMED = "policy_malformed"


@dataclass(frozen=True)
class Decision:
    allow: bool
    reason: str
    policy_version: str | None
    obligations: dict[str, Any] = field(default_factory=dict)
    #: True when the deny came from the client (dependency failure), not from the bundle. The route
    #: maps this to 503 rather than 404 so an outage is not reported as a missing resource.
    unavailable: bool = False

    @property
    def allowed_fields(self) -> list[str] | None:
        fields = self.obligations.get("allowed_fields")
        if isinstance(fields, list) and all(isinstance(f, str) for f in fields):
            return fields
        return None

    @property
    def max_results(self) -> int | None:
        value = self.obligations.get("max_results")
        return value if isinstance(value, int) and value > 0 else None


def _deny(reason: str, *, unavailable: bool = False) -> Decision:
    return Decision(allow=False, reason=reason, policy_version=None, unavailable=unavailable)


class PolicyClient:
    def __init__(self, url: str, timeout_ms: int = 250) -> None:
        self._url = url
        self._timeout = timeout_ms / 1000.0
        self._client = httpx.Client(timeout=self._timeout)

    def close(self) -> None:
        self._client.close()

    def decide(
        self,
        *,
        subject: dict[str, Any],
        action: str,
        resource: dict[str, Any],
        context: dict[str, Any],
    ) -> Decision:
        payload = {
            "input": {
                "subject": subject,
                "action": action,
                "resource": resource,
                "context": context,
            }
        }

        try:
            response = self._client.post(self._url, json=payload)
        except httpx.TimeoutException:
            logger.warning("policy_timeout", extra={"action": action})
            return _deny(REASON_UNAVAILABLE, unavailable=True)
        except httpx.HTTPError:
            logger.warning("policy_unreachable", extra={"action": action}, exc_info=True)
            return _deny(REASON_UNAVAILABLE, unavailable=True)

        if response.status_code != 200:
            # 500 from OPA means an evaluation error, which includes a rule conflict. Deny.
            logger.warning(
                "policy_bad_status",
                extra={"action": action, "status": response.status_code},
            )
            return _deny(REASON_UNAVAILABLE, unavailable=True)

        try:
            body = response.json()
        except ValueError:
            logger.warning("policy_unparseable", extra={"action": action})
            return _deny(REASON_MALFORMED)

        # An undefined decision document omits "result" entirely. That is a deny, not an error to
        # paper over (SP-DATA-001 §3, failure rule).
        result = body.get("result")
        if not isinstance(result, dict):
            logger.warning("policy_undefined", extra={"action": action})
            return _deny(REASON_MALFORMED)

        allow = result.get("allow")
        reason = result.get("reason")
        policy_version = result.get("policy_version")

        # `allow is True` and not a truthy check: a non-empty string or 1 must not authorize.
        if allow is not True and allow is not False:
            logger.warning("policy_malformed_allow", extra={"action": action})
            return _deny(REASON_MALFORMED)
        if not isinstance(reason, str) or not reason:
            return _deny(REASON_MALFORMED)
        if not isinstance(policy_version, str) or not policy_version:
            return _deny(REASON_MALFORMED)

        obligations = result.get("obligations")
        if obligations is None:
            obligations = {}
        elif not isinstance(obligations, dict):
            return _deny(REASON_MALFORMED)

        return Decision(
            allow=allow is True,
            reason=reason,
            policy_version=policy_version,
            obligations=obligations,
        )

    def healthy(self) -> bool:
        try:
            response = self._client.get(
                self._url.rsplit("/v1/data/", 1)[0] + "/health", timeout=2.0
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False
