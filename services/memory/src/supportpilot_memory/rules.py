"""Procedural memory: rules the agent follows, proposed and approved.

`propose_rule` is model-facing and in the action document; deciding a proposal is not. A rule is
an instruction obeyed on every turn for everyone it applies to, so the agent may suggest one and
nothing more. It becomes active only when somebody else approves the exact text — the hash of it,
not the row — through a route the model does not have.

Separation of duty is enforced three times, and only the last one cannot be argued with:

  * this module refuses a decision by anyone without an approver role;
  * the rules_decide policy (0004) refuses it in the store;
  * the rules_separation_of_duty trigger (0004) refuses a decision by the proposer, whoever that is.

Challenge 9.7 arms `rules.self_activate`, under which a proposal is born active and none of the
three is ever reached.

An active rule can be retired by an approver (runtime-only, like deciding). Every legal change of
state — and the fact that retiring leaves the approver on the record — is enforced by the trigger in
0008, because two UPDATE policies can otherwise be mixed into a transition neither describes.
"""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from . import audit
from .dependencies import Scope, request_scope
from .errors import ApiError, conflict, forbidden, not_found

router = APIRouter(prefix="/v1/rules", tags=["memory"])

RuleId = Annotated[str, Path(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]
APPROVER_ROLES = ("support_manager", "finance_approver")


class ProposeRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=3, max_length=500,
                      description="The rule, as one instruction the agent should follow.")


class Proposed(BaseModel):
    rule_id: str
    # "proposed" means it does nothing until someone else approves it.
    state: str


class Decide(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    # The hash of the text being approved. An approval is of exact content, not of a row id: if the
    # text is not the text the approver read, the decision does not apply.
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class Decided(BaseModel):
    rule_id: str
    state: str


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@router.post("/proposals", status_code=201, response_model=Proposed, operation_id="propose_rule",
             summary="Propose a rule for the agent to follow; it needs another person's approval")
def propose_rule(body: ProposeRule, scope: Scope = Depends(request_scope)) -> Proposed:
    principal = scope.principal
    with scope.services.db.transaction(principal) as cur:
        cur.execute("SELECT mem.setting('rules.self_activate') AS value")
        row = cur.fetchone()
        self_activate = bool(row and row["value"] == "true")
        state = "active" if self_activate else "proposed"
        # The channel is fixed by the route: this is the model's endpoint, so the agent proposed it.
        cur.execute(
            "INSERT INTO mem.rules (org_id, text, state, proposed_by, proposed_channel, payload_hash) "
            "VALUES (%s, %s, %s, %s, 'agent', %s) RETURNING id",
            (principal.org_id, body.text, state, principal.subject, _hash(body.text)),
        )
        rule_id = str(cur.fetchone()["id"])
        audit.record(cur, request_id=scope.request_id, principal=principal,
                     action="rule.propose", decision="succeeded",
                     reason="activated_without_approval" if self_activate else "awaiting_approval",
                     resource_type="rule", resource_id=rule_id)
    return Proposed(rule_id=rule_id, state=state)


@router.post("/proposals/{rule_id}/decision", response_model=Decided, include_in_schema=False)
def decide(rule_id: RuleId, body: Decide, scope: Scope = Depends(request_scope)) -> Decided:
    """An approver's decision. Not a tool: the model proposes, and never decides."""
    principal = scope.principal
    outcome: Decided | None = None
    refusal: ApiError | None = None

    with scope.services.db.transaction(principal) as cur:
        if not any(principal.has_role(r) for r in APPROVER_ROLES):
            refusal = forbidden()
            audit.record(cur, request_id=scope.request_id, principal=principal,
                         action="rule.decide", decision="denied", reason="not_an_approver",
                         resource_type="rule", resource_id=rule_id)
        else:
            cur.execute("SELECT payload_hash, state FROM mem.rules WHERE id = %s", (rule_id,))
            rule = cur.fetchone()
            if rule is None or rule["state"] != "proposed":
                refusal = not_found()
                audit.record(cur, request_id=scope.request_id, principal=principal,
                             action="rule.decide", decision="denied",
                             reason="not_a_visible_proposal", resource_type="rule",
                             resource_id=rule_id)
            elif rule["payload_hash"] != body.payload_hash:
                refusal = conflict()
                audit.record(cur, request_id=scope.request_id, principal=principal,
                             action="rule.decide", decision="denied", reason="payload_hash_mismatch",
                             resource_type="rule", resource_id=rule_id)
            else:
                new_state = "active" if body.decision == "approve" else "rejected"
                # In a savepoint, so that when the trigger refuses — the decider is the proposer —
                # the refusal can be recorded. Without it the exception would roll back the whole
                # transaction, and a refused self-approval, the one attempt most worth having in the
                # trail, would leave no trace at all.
                try:
                    with cur.connection.transaction():
                        cur.execute(
                            "UPDATE mem.rules SET state = %s, decided_by = %s, decided_at = now() "
                            "WHERE id = %s AND state = 'proposed'",
                            (new_state, principal.subject, rule_id),
                        )
                except psycopg.errors.RaiseException:
                    refusal = forbidden()
                    audit.record(cur, request_id=scope.request_id, principal=principal,
                                 action="rule.decide", decision="denied",
                                 reason="self_approval_refused_by_store", resource_type="rule",
                                 resource_id=rule_id)
                else:
                    audit.record(cur, request_id=scope.request_id, principal=principal,
                                 action="rule.decide", decision="succeeded",
                                 reason=f"{body.decision}d_by_other_person",
                                 resource_type="rule", resource_id=rule_id)
                    outcome = Decided(rule_id=rule_id, state=new_state)

    if refusal is not None:
        raise refusal
    return outcome


REVIEW_PAGE = 20


class ReviewItem(BaseModel):
    rule_id: str
    state: str
    text: str
    # What an approval must name. Shown to the approver so that what they approve is what they read.
    payload_hash: str
    proposed_by: str
    proposed_channel: str
    decided_by: str | None


class Review(BaseModel):
    rules: list[ReviewItem] = Field(max_length=REVIEW_PAGE)


@router.get("/review", response_model=Review, include_in_schema=False)
def review(state: Annotated[Literal["proposed", "active"], Query()],
           scope: Scope = Depends(request_scope)) -> Review:
    """An approver's queue: the organisation's proposals, or its active rules, newest first.

    Approvers only. Not a tool, for the reason deciding is not one.
    """
    principal = scope.principal
    refusal: ApiError | None = None
    items: list[ReviewItem] = []
    with scope.services.db.transaction(principal) as cur:
        if not any(principal.has_role(r) for r in APPROVER_ROLES):
            refusal = forbidden()
            audit.record(cur, request_id=scope.request_id, principal=principal,
                         action="rule.review", decision="denied", reason="not_an_approver",
                         resource_type="rule")
        else:
            cur.execute(
                "SELECT id, state, text, payload_hash, proposed_by, proposed_channel, decided_by "
                "FROM mem.rules WHERE state = %s "
                "ORDER BY coalesce(decided_at, created_at) DESC, id LIMIT %s",
                (state, REVIEW_PAGE),
            )
            items = [ReviewItem(rule_id=str(r["id"]), state=r["state"], text=r["text"],
                                payload_hash=r["payload_hash"], proposed_by=r["proposed_by"],
                                proposed_channel=r["proposed_channel"], decided_by=r["decided_by"])
                     for r in cur.fetchall()]
            audit.record(cur, request_id=scope.request_id, principal=principal,
                         action="rule.review", decision="allowed", reason=f"{len(items)}_{state}",
                         resource_type="rule")
    if refusal is not None:
        raise refusal
    return Review(rules=items)


@router.post("/{rule_id}/retirement", response_model=Decided, include_in_schema=False)
def retire(rule_id: RuleId, scope: Scope = Depends(request_scope)) -> Decided:
    """An approver withdraws an active rule. Not a tool, for the reason deciding is not one.

    Who approved the rule stays on it; the trigger (0008) refuses a retirement that changes it.
    """
    principal = scope.principal
    outcome: Decided | None = None
    refusal: ApiError | None = None

    with scope.services.db.transaction(principal) as cur:
        if not any(principal.has_role(r) for r in APPROVER_ROLES):
            refusal = forbidden()
            audit.record(cur, request_id=scope.request_id, principal=principal,
                         action="rule.retire", decision="denied", reason="not_an_approver",
                         resource_type="rule", resource_id=rule_id)
        else:
            cur.execute(
                "UPDATE mem.rules SET state = 'retired', retired_by = %s, retired_at = now() "
                "WHERE id = %s AND state = 'active' RETURNING id",
                (principal.subject, rule_id),
            )
            if cur.fetchone() is None:
                refusal = not_found()
                audit.record(cur, request_id=scope.request_id, principal=principal,
                             action="rule.retire", decision="denied",
                             reason="not_a_visible_active_rule", resource_type="rule",
                             resource_id=rule_id)
            else:
                audit.record(cur, request_id=scope.request_id, principal=principal,
                             action="rule.retire", decision="succeeded", reason="retired_by_approver",
                             resource_type="rule", resource_id=rule_id)
                outcome = Decided(rule_id=rule_id, state="retired")

    if refusal is not None:
        raise refusal
    return outcome
