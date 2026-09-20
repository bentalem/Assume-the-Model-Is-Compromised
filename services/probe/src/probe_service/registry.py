"""The request registry — every API request this service can make.

The same shape as the Range's mutation registry, one level up. A caller sends an id; there is no
endpoint that takes a method, a path, a header or a body. Adding a request is a change to this file
and therefore a change somebody reviews, which is the entire security property.

What a probe returns is deliberately thin: the status code, the error code the API reported, and
the *names* of the fields in the response. Not the values. A challenge that needs to show data reads
it from the database through a Range observation, where the row cap and the field list are already
enforced — and a probe that returned bodies would be a second, unbounded way to read the same data.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Probe:
    id: str
    summary: str
    user: str
    method: str
    path: str
    # Why this request exists, shown in the Range's result panel so a learner can see what was asked
    # without being able to ask for anything else.
    intent: str = ""


def _p(*args, **kwargs) -> tuple[str, Probe]:
    probe = Probe(*args, **kwargs)
    return probe.id, probe


PROBES: dict[str, Probe] = dict(
    [
        # ------------------------------------------------------------------------------------
        # Track 1 · identity
        # ------------------------------------------------------------------------------------
        _p(
            "alice.read.own_order",
            "alice reads ORD-2001, her own tenant's order",
            "alice", "GET", "/v1/orders/ORD-2001",
            intent="The control group: a request that should succeed.",
        ),
        _p(
            "alice.read.foreign_order",
            "alice reads ORD-3001, which belongs to northwind",
            "alice", "GET", "/v1/orders/ORD-3001",
            intent="Cross-tenant. Indistinguishable from an order that does not exist.",
        ),
        _p(
            "mallory.read.cedar_order",
            "mallory, who is northwind-only, reads cedar's ORD-2001",
            "mallory", "GET", "/v1/orders/ORD-2001",
            intent="The same boundary from the other side.",
        ),
        # ------------------------------------------------------------------------------------
        # Track 3 · authorization and field obligations
        # ------------------------------------------------------------------------------------
        _p(
            "alice.read.restricted_customer",
            "alice, a support agent, reads the restricted customer CUS-4003",
            "alice", "GET", "/v1/customers/CUS-4003",
            intent="Permitted, with fields removed by a policy obligation.",
        ),
        _p(
            "bob.read.restricted_customer",
            "bob, a manager, reads the same restricted customer",
            "bob", "GET", "/v1/customers/CUS-4003",
            intent="The same record, a different field set. Compare the field lists.",
        ),
        _p(
            "fiona.read.order",
            "fiona, who approves refunds, tries to read an order",
            "fiona", "GET", "/v1/orders/ORD-2001",
            intent="Same tenant, wrong role. A refusal that is about the role, not the record.",
        ),
    ]
)
