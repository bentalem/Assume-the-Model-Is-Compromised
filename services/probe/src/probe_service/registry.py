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
    # The request body, as the exact bytes to send, for the one probe that is not a GET.
    #
    # A string rather than a dict, and not by accident. A structure assembled at call time is a
    # structure somebody can be tempted to assemble from an argument; a literal here is the same
    # thing the reviewer of this file read. Nothing composes it and no caller can supply one — the
    # rule that makes this registry worth having applies to bodies exactly as it does to paths.
    body: str | None = None


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
        # The service account, asking the same two questions alice asks. Unarmed it holds no
        # membership anywhere and both come back 404; armed it holds both tenants and both succeed.
        _p(
            "agent.read.cedar_order",
            "the service account reads cedar's order",
            "agent-service", "GET", "/v1/orders/ORD-2001",
            intent="One credential, cedar's data.",
        ),
        _p(
            "agent.read.northwind_order",
            "the service account reads northwind's order",
            "agent-service", "GET", "/v1/orders/ORD-3001",
            intent="The same credential, the other tenant's data. alice cannot do this.",
        ),
        _p(
            "alice.read.tkt_1001",
            "alice reads the ticket that carries ten planted injections",
            "alice", "GET", "/v1/tickets/TKT-1001",
            intent="Untrusted text arriving through a completely ordinary, permitted request.",
        ),
        _p(
            "fiona.read.order",
            "fiona, who approves refunds, tries to read an order",
            "fiona", "GET", "/v1/orders/ORD-2001",
            intent="Same tenant, wrong role. A refusal that is about the role, not the record.",
        ),
        # ------------------------------------------------------------------------------------
        # Track 7 · the request that never reached a control (7.3)
        #
        # The only probe here that is not a GET, and the only one whose point is that it fails
        # before anything decides. alice is a support agent in cedar, ORD-2001 is cedar's, and
        # every other field is one she is entitled to send — the `reason` is a string where the
        # schema declares an enumeration, and nothing else is wrong with it.
        #
        # So the API refuses it in the validation handler, returns 400 with the offending field
        # named, and writes no audit row, because at that moment there is no subject, no resource
        # and no decision to record. 7.3 asks a learner to find that absence, and a challenge that
        # printed a log line for a request the lab had never made was asking them to take it on
        # trust.
        #
        # The body is fixed and it is invalid on purpose. That is what makes this safe to leave in
        # a registry: it cannot create a refund proposal, because it cannot get past the schema.
        # Anyone editing it into a well-formed body is adding a probe that moves the lab's state,
        # which is a different thing and belongs in a mutation with a restore.
        _p(
            "alice.propose.invalid_reason",
            "alice proposes a refund with a reason outside the enumeration",
            "alice", "POST", "/v1/actions/refunds",
            intent="Refused by schema validation, before any control was consulted. Creates nothing.",
            body=(
                '{"order_number":"ORD-2001","amount":"12.00",'
                '"currency":"USD","reason":"damaged item"}'
            ),
        ),
    ]
)


# ==================================================================================================
# Track 1 · tokens that are wrong in exactly one way
#
# These do not ask Keycloak for anything unusual. They take a genuine token for a genuine user and
# change one thing about it, so the request differs from a working one in exactly one respect. That
# is what makes the result mean something: if a tampered token is refused and an untampered one is
# accepted, the refusal is about the tampering.
#
# `transform` names a function in main.py. It is a fixed identifier from this file, never a caller's
# string — the same rule as everything else here.
# ==================================================================================================

TAMPERED: dict[str, tuple[str, str, str]] = {
    # id -> (base user, transform name, what the learner should notice)
    "alice.token.unsigned": (
        "alice", "strip_signature",
        "The same claims, with alg set to none and the signature removed.",
    ),
    "alice.token.resigned": (
        "alice", "resign_with_attacker_key",
        "The same claims, re-signed with a key the attacker chose.",
    ),
    "alice.token.claimed_org": (
        "alice", "claim_other_organization",
        "organization_id rewritten to the other tenant, then re-signed.",
    ),
}

# A genuine, correctly signed, unexpired token — minted for a different service in the same realm.
#
# Nothing is tampered with here, which is what makes it the interesting case: every check except one
# passes. The client is declared in the realm file with no audience mapper, so its tokens simply do
# not name the SupportPilot API.
WRONG_AUDIENCE = {
    "alice.token.other_service": (
        "alice", "another-service",
        "A valid token for a different service. Nothing about it is forged.",
    ),
}


# ------------------------------------------------------------------------------------------------
# Enumerations — a sequence of legal requests, for challenge 4.3.
#
# Every other probe is one request. This is a handful of them, following the cursor the API returns,
# because the thing 4.3 demonstrates cannot be shown in a single call: each call is inside the page
# cap, correctly authorised and correctly logged, and the extraction is the product of repeating it.
#
# What comes back is counts, never records. Same rule as every other probe and it matters more here:
# a probe that returned the pages would be exactly the bulk-read channel this challenge is about.
# ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Enumeration:
    id: str
    summary: str
    user: str
    path: str
    query: str
    # A ceiling on this service, not on the API. The API has no per-session limit, which is the
    # finding; without a ceiling here the probe would page until the directory ran out.
    max_pages: int
    intent: str = ""


ENUMERATIONS: dict[str, Enumeration] = {
    "alice.enumerate.customers": Enumeration(
        id="alice.enumerate.customers",
        summary="Page the customer directory with one two-character query",
        user="alice",
        path="/v1/customers",
        query="ar",
        max_pages=12,
        intent="Every call is within the page cap, permitted, and logged as allowed.",
    ),
}
