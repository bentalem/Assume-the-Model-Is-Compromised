"""The authorization pipeline every tool goes through.

The order is fixed by SP-PLAN-003 §10 and must not be reordered:

    validate schema -> verify token -> load subject -> load trusted resource
    -> build policy input -> ask OPA -> transaction + context -> query
    -> apply obligations -> audit -> commit -> bounded response

Routes do not call OPA or the repositories directly. They describe *what* they need
(`AuthorizedRequest`) and this module performs the sequence, so a new tool cannot accidentally skip
a step. Adding a tool means adding a route that goes through `authorize`; there is no other way in.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .audit.writer import AuditEvent, AuditWriter
from .auth.tokens import VerifiedToken
from .errors import not_found, unavailable
from .policy.client import Decision, PolicyClient
from .repositories.memberships import Subject

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResourceContext:
    """A trusted resource, loaded from the database before policy evaluation."""

    type: str
    id: str
    organization_id: str
    attributes: dict[str, Any]

    def as_policy_input(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "id": self.id,
            "organization_id": self.organization_id,
            **self.attributes,
        }


@dataclass(frozen=True)
class Authorization:
    """The outcome of a successful authorization: who, where, and what may be returned."""

    subject: Subject
    resource: ResourceContext
    decision: Decision

    @property
    def organization_id(self) -> str:
        return self.resource.organization_id

    def minimize(self, record: dict[str, Any]) -> dict[str, Any]:
        """Apply the policy's field obligations.

        Whitelist, not blacklist: a field the policy did not name is removed even if the repository
        returned it and the response model would have accepted it.
        """
        allowed = self.decision.allowed_fields
        if allowed is None:
            return record
        return {key: value for key, value in record.items() if key in allowed}


class Pipeline:
    def __init__(self, policy: PolicyClient, audit: AuditWriter) -> None:
        self._policy = policy
        self._audit = audit

    def authorize(
        self,
        *,
        request_id: str,
        token: VerifiedToken,
        subject: Subject | None,
        action: str,
        resource: ResourceContext | None,
        resource_type: str,
        resource_id: str,
    ) -> Authorization:
        """Run the authorization steps, or raise.

        A denial always produces an audit event before the error is raised, so a refused request is
        as well evidenced as a permitted one (SP-PRD-001 FR-06).
        """
        actor_id = subject.user_id if subject else token.subject

        def deny(reason: str, organization_id: str | None) -> None:
            self._safe_audit(
                AuditEvent(
                    request_id=request_id,
                    actor_id=actor_id,
                    organization_id=organization_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    decision="denied",
                    reason=reason,
                )
            )

        # A verified token whose subject has no application user is authenticated but unknown here.
        if subject is None:
            deny("unknown_subject", None)
            raise not_found()

        # No trusted resource means the caller cannot see it, or it does not exist. The same answer
        # is given for both, so the response never confirms existence in another tenant.
        if resource is None:
            deny("resource_not_visible", None)
            raise not_found()

        decision = self._policy.decide(
            subject={
                "id": subject.user_id,
                "organizations": subject.organizations,
                "roles": subject.roles_in(resource.organization_id),
                "authentication_level": subject.authentication_level,
            },
            action=action,
            resource=resource.as_policy_input(),
            context={
                "request_id": request_id,
                "occurred_at": datetime.now(UTC).isoformat(),
                "network_zone": "internal",
            },
        )

        if not decision.allow:
            self._safe_audit(
                AuditEvent(
                    request_id=request_id,
                    actor_id=actor_id,
                    organization_id=resource.organization_id,
                    action=action,
                    resource_type=resource.type,
                    resource_id=resource.id,
                    decision="denied",
                    reason=decision.reason,
                    policy_version=decision.policy_version,
                )
            )
            # A dependency failure is a 503; a policy denial is a 404. Reporting an outage as
            # "not found" would hide it, and reporting a denial as an outage would invite a retry.
            raise unavailable() if decision.unavailable else not_found()

        return Authorization(subject=subject, resource=resource, decision=decision)

    def record_success(
        self,
        *,
        request_id: str,
        auth: Authorization,
        action: str,
        result_reference: str | None = None,
    ) -> None:
        self._safe_audit(
            AuditEvent(
                request_id=request_id,
                actor_id=auth.subject.user_id,
                organization_id=auth.organization_id,
                action=action,
                resource_type=auth.resource.type,
                resource_id=auth.resource.id,
                decision="allowed",
                reason=auth.decision.reason,
                policy_version=auth.decision.policy_version,
                result_reference=result_reference,
            )
        )

    def _safe_audit(self, event: AuditEvent) -> None:
        """Write a standalone audit event.

        Used only for events with no business effect attached — denials and completed reads. A
        failure here is logged loudly but does not convert an already-correct denial into a 500;
        the caller is still refused. Evidence bound to an *effect* uses `record_in` inside that
        effect's transaction instead, where a failure does roll the effect back.
        """
        try:
            self._audit.record(event)
        except Exception:
            logger.error(
                "audit_write_failed",
                extra={"request_id": event.request_id, "action": event.action},
                exc_info=True,
            )
