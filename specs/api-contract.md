# API contract

Normative for `services/api/` and `openapi/supportpilot-actions.yaml`. Every operation here is
callable by the model through Onyx; nothing else is.

## The request pipeline

Every endpoint executes these steps in this order. No step may be skipped, reordered, or made
conditional.

```
1  validate request schema            → 400, no lookup performed
2  verify token                       → 401, before any database access
3  load subject + memberships          (SET LOCAL app.user_id only)
4  load trusted resource attributes    (organization_id comes from HERE, never from the request)
5  build policy input                  (subject, action, resource, context)
6  call OPA                           → deny ⇒ audit + 404/403
7  BEGIN; SET LOCAL user + org context
8  parameterized query / write
9  apply policy field obligations
10 INSERT audit event                  (same transaction)
11 COMMIT
12 serialize bounded response
```

If step 10 fails, step 11 never happens — no effect without evidence.

## Conventions

- **Base path** `/v1`. All responses `application/json`.
- **Auth** `Authorization: Bearer <user access token>` on every endpoint. No API key, no service token.
- **Correlation** `X-Request-Id` accepted and echoed; generated if absent; recorded on every audit row.
- **Pagination** cursor-based: `limit` (default 20, max 50) and `cursor`. Never offset over a
  tenant-filtered set.
- **No field in any request body or path may be `user_id`, `organization_id`, `role`, `author_id`,
  `approved`, or `state`.** These are derived server-side. A request carrying one is rejected as a
  schema violation, not silently ignored.

### Error model

```json
{ "error": { "code": "not_found", "request_id": "req-123" } }
```

A `400 invalid_request` carries one extra field, and only that code does:

```json
{ "error": { "code": "invalid_request", "request_id": "req-123",
             "rejected": [ { "field": "body.amount", "error": "string_type" } ] } }
```

`field` and `error` name which part of the request failed and how. **The submitted value is never
included** — a rejected body is attacker-influenced content, and echoing it back is how a validation
handler becomes a reflection gadget. The field path and the error type are already implied by the
published action document, so naming them tells the caller nothing it was not given.

This is deliberate and it is not a relaxation. A caller that cannot tell a number sent where a
string was required from a field it invented cannot correct itself, and neither can the operator
reading the logs: three different mistakes arriving as one indistinguishable word is a dead end, not
a control. The same rejection is logged, with the same two fields and the same omission.

| HTTP | `code` | Used for |
|---|---|---|
| 400 | `invalid_request` | Schema, pattern, range, or enum violation |
| 401 | `unauthenticated` | Missing, malformed, expired, wrong-issuer/audience token |
| 403 | `forbidden` | Authenticated but not permitted for a **visible** resource |
| 404 | `not_found` | Unknown resource **or** a resource in another tenant |
| 409 | `conflict` | Stale-state write, duplicate idempotency key |
| 422 | `business_rule` | Valid schema, rejected by a business limit (e.g. amount over cap) |
| 429 | `rate_limited` | Per-user or per-session budget exceeded |
| 503 | `unavailable` | OPA, database, or a dependency is unavailable |

> **404 vs 403:** a cross-tenant request returns **404**, identical to an unknown identifier. A 403
> would confirm the resource exists in another tenant. Never let the status code leak existence.
>
> Error bodies carry no schema names, SQL, resource details, or policy internals — only `code` and
> `request_id`.

## Read operations

### `GET /v1/orders/{order_number}` — `get_order`

| | |
|---|---|
| Action | `order.read` |
| Path | `order_number` — `^ORD-[0-9]{4,12}$` |
| Query | `include` — optional, `items` and/or `shipment` (phase 2) |

```json
{
  "order_number": "ORD-2001",
  "status": "shipped",
  "currency": "USD",
  "total_amount": "149.90",
  "placed_at": "2026-08-14T09:12:00Z",
  "updated_at": "2026-08-16T11:02:00Z",
  "items": [{ "sku": "SKU-8812", "description": "Cable, 2m", "quantity": 1, "unit_amount": "149.90" }],
  "shipment": { "status": "in_transit", "carrier": "ACME", "tracking_ref": "1Z-REDACTED" }
}
```

Fields are subject to policy obligations — `allowed_fields` removes anything not listed, before
serialization and before logging.

### `GET /v1/customers` — `search_customers`

| | |
|---|---|
| Action | `customer.search` |
| Query | `q` (2–80 chars), `limit` (≤ 50), `cursor` |

Returns `{ "results": [...], "next_cursor": "..."|null }`. `results` carries only
`customer_ref`, `full_name`, `assigned_team`. Never email, never a full record. Pagination is
mandatory — there is no "return everything" mode (`TS7-09`).

### `GET /v1/customers/{customer_ref}` — `get_customer`

Action `customer.read`. Returns the approved subset: `customer_ref`, `full_name`, `email`,
`assigned_team`, `open_ticket_count`. A `restricted` sensitivity customer returns fewer fields by
policy obligation, not by client request.

### `GET /v1/tickets/{ticket_number}` — `get_ticket`

| | |
|---|---|
| Action | `ticket.read` |
| Path | `ticket_number` — `^TKT-[0-9]{4,12}$` |
| Query | `limit`, `cursor` for messages |

Returns ticket header plus **permitted** messages. `visibility = 'restricted'` messages are excluded
for `support_agent` at the database policy layer, not by application filtering.

> Message bodies are untrusted content. They are returned as data for the model to summarize. They
> never alter tool availability, authorization, or instructions (`TS7-03`, `TS7-04`).

## Write operation

### `POST /v1/tickets/{ticket_number}/notes` — `add_internal_note`

| | |
|---|---|
| Action | `note.create` |
| Body | `{ "body": "string, 1–4000 chars", "expected_ticket_status": "open" }` |

- `author_id` is **not** in the schema. It comes from the verified token and is enforced by the
  database insert policy.
- `expected_ticket_status` implements the stale-write check — a mismatch returns `409 conflict`
  rather than writing against a changed ticket.
- Returns `{ "note_id": "...", "created_at": "..." }`. The note body is not echoed.

## Action operations

### `POST /v1/actions/refunds` — `propose_refund`

**This creates a proposal. It moves no money.**

```json
{
  "order_number": "ORD-2001",
  "amount": "49.90",
  "currency": "USD",
  "reason": "damaged_on_arrival",
  "note": "optional free text, ≤ 500 chars"
}
```

| Field | Rule |
|---|---|
| `order_number` | `^ORD-[0-9]{4,12}$`; must resolve in the caller's tenant |
| `amount` | Decimal string, > 0, ≤ order total, ≤ `ACTION_MAX_AMOUNT`, ≤ the role's policy limit |
| `currency` | Must equal the order's currency; no conversion is ever performed |
| `reason` | Enum: `damaged_on_arrival`, `not_delivered`, `wrong_item`, `duplicate_charge`, `other` |

Server behavior: validate → load order → policy check `refund.propose` → compute
`payload_hash = sha256(canonical_json(payload))` → insert `action_requests` in `PROPOSED`, move to
`PENDING_APPROVAL`, set `expires_at` → audit → commit.

```json
{ "action_id": "9c1f...", "state": "PENDING_APPROVAL", "expires_at": "2026-12-09T12:00:00Z" }
```

Response 422 `business_rule` when an amount exceeds a limit — never a silent clamp to the maximum.

### `GET /v1/actions/{action_id}` — `get_action_status`

Action `action.read`. Visible to the requester and to authorized roles in the same tenant.

```json
{
  "action_id": "9c1f...",
  "action_type": "refund",
  "state": "SUCCEEDED",
  "amount": "49.90",
  "currency": "USD",
  "created_at": "...",
  "decided_at": "...",
  "completed_at": "...",
  "provider_reference": "re_1P..."
}
```

Never returns `payload_hash`, approver identity, internal job state, lease data, or provider response
bodies.

## Endpoints the model can never reach

These exist but are **not** in `openapi/supportpilot-actions.yaml` and are not registered as Onyx
actions. They require an approver or operator token and are reachable only from the approval portal
or internal networks.

| Endpoint | Purpose | Caller |
|---|---|---|
| `GET /internal/approvals` | Pending queue with full payload | Approval portal |
| `POST /internal/approvals/{action_id}` | Record approve or reject | Approval portal |
| `GET /healthz`, `/readyz` | Liveness and readiness | Orchestrator |

`POST /internal/approvals/{action_id}` re-checks the approver's **current** authorization at decision
time, refuses self-approval by policy, and stores `approved_hash` equal to the request's
`payload_hash`. It cannot modify the payload — there is no field for it.

## OpenAPI document rules

- Only the operations in the read/write/action sections above.
- Every operation: narrow `operationId`, clear `summary`, strict request schema, **bounded** response
  schema. No `additionalProperties: true`, no untyped `object`, no unbounded `array`.
- Every string parameter has a `pattern` or `maxLength`.
- Documented responses: `200`, `400`, `401`, `404`, `409`, `422`, `429`, `503` — no default catch-all.
- Individual OAuth configured so the user identity reaches the API.

## Agent instruction constraints

The Onyx agent instructions may state when to use a tool and how to report an error. They must not:

- claim the agent has authority the API does not grant;
- instruct the model to retry a denied call with different arguments;
- describe internal identifiers, table names, or policy structure;
- promise that a refund will be executed — only that a proposal was created.

Budgets from `AGENT_MAX_TOOL_CALLS` and the time, token, and cost limits apply per user turn
(`T-014`).

## Per-endpoint test obligation

No endpoint merges without, at minimum:

| Case | Expectation |
|---|---|
| Positive, in tenant | 200 with only the approved fields |
| Cross-tenant identifier | 404, identical shape to unknown |
| Malformed identifier | 400 before any lookup |
| Missing / wrong-audience token | 401 before policy and database access |
| OPA unavailable | 503, no fallback allow |
| Injected instruction in returned content | No change to tool availability or authorization |
