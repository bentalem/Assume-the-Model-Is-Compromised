# SupportPilot — Architecture

A multi-tenant AI support agent, built so that every control can be removed and the resulting
failure observed.

> **The core rule:** the model may *propose* tool use. Trusted services decide what is allowed, and
> trusted services perform every real action.

Everything below follows from that one sentence. If you read nothing else, read the two diagrams in
[The shape of the system](#the-shape-of-the-system) and [What actually decides](#what-actually-decides).

---

## The shape of the system

Seven components on four networks. The networks are the first control: most of the isolation in
this system is enforced by the fact that two containers simply cannot reach each other.

```mermaid
flowchart TB
    user([Support agent<br/>in a browser])
    approver([Approver<br/>in a browser])

    subgraph edge["🌐 edge — user-facing"]
        keycloak[Keycloak<br/>identity provider<br/>:8080 / :8443]
        portal[Approval portal<br/>:8090]
    end

    subgraph app["app — internal, no internet"]
        onyx[Onyx<br/>agent platform<br/>separate compose project]
        api[SupportPilot API<br/>no published port]
    end

    subgraph policy["policy — internal, no internet"]
        opa[OPA<br/>policy decision point]
    end

    subgraph data["data — internal, no internet"]
        pg[(PostgreSQL<br/>row-level security)]
        worker[Worker<br/>executes approved actions]
        migrate[Migrate<br/>runs once, then exits]
    end

    user --> keycloak
    user --> onyx
    approver --> portal

    onyx -->|"user's OAuth token"| api
    portal -->|"approver's token"| api
    api -->|"allow / deny"| opa
    api -->|"sp_api_role"| pg
    worker -->|"sp_worker_role"| pg
    migrate -->|"sp_migrator_role"| pg
    api -.->|"verify token"| keycloak

    style edge fill:#1e3a5f,stroke:#4a90d9,color:#fff
    style app fill:#2d2d5f,stroke:#7b7bd9,color:#fff
    style policy fill:#4a2d5f,stroke:#b07bd9,color:#fff
    style data fill:#1e4a3a,stroke:#4ad990,color:#fff
```

Read the arrows that are **missing**, because they are the design:

| Missing arrow | Why it matters |
|---|---|
| Onyx → PostgreSQL | The agent platform has no database credential at all |
| Approval portal → PostgreSQL | A portal that could reach the database could edit an approved payload |
| Approval portal → OPA | The portal enforces nothing; it renders and forwards |
| Worker → OPA | The worker makes no authorization decisions; it re-verifies facts already recorded |
| Worker → API | Execution is not reachable from the request path |
| Anything → OPA except the API | The policy network holds exactly one consumer |

That last column is not documentation — it is a test. Check `V-02` in the verification script:
*postgres and opa unreachable from the approval portal.*

---

## Who is who

| Component | Runs as | On networks | What it must never do |
|---|---|---|---|
| **Onyx** | its own compose project | `app` | Touch the database, or decide authorization |
| **The model** | inside Onyx | — | Hold a credential, approve anything, execute anything |
| **Keycloak** | `quay.io/keycloak` | `edge`, `app` | — |
| **API** | `sp_api_role` | `app`, `policy`, `data` | Execute a protected financial effect in the request path |
| **OPA** | — | `policy` | Query business data, or enforce anything |
| **PostgreSQL** | — | `data` | Accept a connection from Onyx or the public network |
| **Approval portal** | no credential | `edge`, `app` | Modify a payload after approval |
| **Worker** | `sp_worker_role` | `data` | Read business data, or take instructions from a model |
| **Migrate** | `sp_migrator_role` | `data` | Run continuously, or leave its credential in a running service |

The API has **no published port**. It is reachable only from inside the `app` network. You cannot
curl it from your laptop, which is deliberate: every request must arrive the way a real one does.

---

## What actually decides

A tool call passes through five independent checks. Any one of them can say **no**. None of them
can say *"yes, skip the rest."*

```mermaid
flowchart LR
    A[Tool call<br/>arrives] --> B{1 · Schema<br/>valid?}
    B -->|no| X1[400]
    B -->|yes| C{2 · Token<br/>valid?}
    C -->|no| X2[401]
    C -->|yes| D{3 · Resource<br/>visible?}
    D -->|no| X3[404]
    D -->|yes| E{4 · Policy<br/>allows?}
    E -->|no| X4[404]
    E -->|unreachable| X5[503]
    E -->|yes| F{5 · RLS<br/>row matches?}
    F -->|no rows| X6[404]
    F -->|match| G[Minimize fields<br/>→ audit → return]

    style X1 fill:#5f1e1e,stroke:#d94a4a,color:#fff
    style X2 fill:#5f1e1e,stroke:#d94a4a,color:#fff
    style X3 fill:#5f1e1e,stroke:#d94a4a,color:#fff
    style X4 fill:#5f1e1e,stroke:#d94a4a,color:#fff
    style X5 fill:#5f4a1e,stroke:#d9a44a,color:#fff
    style X6 fill:#5f1e1e,stroke:#d94a4a,color:#fff
    style G fill:#1e4a3a,stroke:#4ad990,color:#fff
```

Three things to notice.

**Every refusal looks the same from outside.** Cross-tenant, non-existent, policy-denied and
RLS-filtered all return `404`. A caller cannot use the error code to learn that a record exists.

**A policy outage is a `503`, not a `404`.** If OPA is unreachable, malformed, timed out, or returns
a non-boolean `allow`, the answer is deny — and the caller is told it is an outage, because
pretending the record does not exist would be a lie that hides a broken control. There is no cached
allow and no local fallback. Stop OPA and try it.

**Identity never comes from the request.** The tenant comes from the token. The roles come from the
database. No tool anywhere takes a `user_id`, `organization_id`, `role` or `approved` parameter —
those fields do not exist in any schema, and an attempt to add one returns `400` rather than being
silently dropped.

### Reading an order, step by step

```mermaid
sequenceDiagram
    participant M as Model
    participant O as Onyx
    participant A as API
    participant K as Keycloak
    participant P as OPA
    participant D as PostgreSQL

    M->>O: get_order("ORD-2001")
    O->>A: GET /v1/orders/ORD-2001<br/>Authorization: the user's own token
    A->>K: verify signature, issuer, audience, expiry
    A->>D: who is this? load roles from memberships
    A->>D: load the order's tenant + attributes
    A->>P: {subject, action, resource, context}
    P-->>A: allow · reason · policy_version · allowed_fields
    A->>D: BEGIN; SET LOCAL app.user_id, app.organization_id
    A->>D: SELECT named columns … (RLS filters again)
    A->>D: INSERT audit_events (same transaction)
    A->>D: COMMIT
    A-->>O: only the fields policy named
    O-->>M: the result
```

The `SET LOCAL` line is the one worth staring at. The tenant context is **transaction-local**, so a
pooled connection cannot carry one user's identity into the next user's query. Check `V-12`:
*context-free read still returned 0 rows after 12 pooled requests.*

---

## Two layers, always

Tenant isolation is enforced twice, by two different systems, for the same request.

```mermaid
flowchart TB
    subgraph L1["Layer 1 · Policy (OPA)"]
        direction LR
        p1["is the subject a member<br/>of the resource's tenant?"]
        p2["does their role permit<br/>this action?"]
        p3["which fields may<br/>come back?"]
    end

    subgraph L2["Layer 2 · PostgreSQL row-level security"]
        direction LR
        r1["organization_id =<br/>app.current_org()"]
        r2["ENABLE + FORCE<br/>row level security"]
        r3["runtime role owns nothing,<br/>holds no BYPASSRLS"]
    end

    L1 --> L2
    L2 --> OK["a row, or nothing"]

    style L1 fill:#4a2d5f,stroke:#b07bd9,color:#fff
    style L2 fill:#1e4a3a,stroke:#4ad990,color:#fff
```

`FORCE` is the detail that makes it real. PostgreSQL exempts a table's **owner** from its own row
policies unless `FORCE` is set — so an application connecting as the role that ran the migrations
gets no filtering at all, while the policies sit in the schema looking perfectly correct. Here the
migration role owns everything and the runtime roles own nothing.

When the two layers disagree, that is an event: if policy allows a read and RLS returns no rows, the
API writes `order.read.rls_empty` to the audit trail before returning `404`. A disagreement between
your two controls should be loud.

### The four database roles

| Role | Holds | Never holds |
|---|---|---|
| `sp_migrator_role` | ownership of schema `app`, all DDL | a credential inside any running service |
| `sp_api_role` | `SELECT` on named tables, `INSERT` on notes / actions / audit | ownership, `BYPASSRLS`, `SUPERUSER`, DDL |
| `sp_worker_role` | job claim + execution state + audit `INSERT` | any grant on customers, orders, tickets, notes |
| `sp_auditor_role` | `SELECT` on `audit_events` | any write, anywhere |

The worker **refuses to start** if it can read a customer. Not a warning — a failed boot.

`audit_events` is append-only by grant: no runtime role holds `UPDATE` or `DELETE` on it, so nothing
in the request path can revise its own history.

---

## Irreversible actions

For anything that moves money, the control is not a stricter check. It is **structure**: the request
path can propose, and only the worker can execute.

```mermaid
stateDiagram-v2
    [*] --> PROPOSED: API creates a record<br/>nothing has happened
    PROPOSED --> PENDING_APPROVAL: payload hashed and stored
    PENDING_APPROVAL --> APPROVED: a different person approves<br/>this exact hash
    PENDING_APPROVAL --> REJECTED: or does not
    APPROVED --> QUEUED: job enqueued in the<br/>same transaction
    QUEUED --> EXECUTING: worker claims it<br/>FOR UPDATE SKIP LOCKED
    EXECUTING --> SUCCEEDED
    EXECUTING --> FAILED
    REJECTED --> [*]
    SUCCEEDED --> [*]
    FAILED --> [*]

    note right of PENDING_APPROVAL
        The API may drive an action
        only this far. QUEUED and
        beyond are worker-only,
        enforced by a row policy.
    end note
```

The model has a tool that can reach `PROPOSED`. It has no tool that can approve, and no tool that
can execute. That is the whole control; the rest is detail.

Before it executes anything, the worker independently re-establishes six facts:

1. it holds an exclusive lease on the job
2. the action is in a state that permits execution
3. an approval decision exists, and it is an approval
4. the approver is not the requester
5. the approval has not expired
6. `sha256(payload)` still matches the stored hash **and** the approved hash

Separation of duty is enforced in three unrelated places — in the policy, by a database trigger, and
by the worker — so no single mistake re-enables self-approval. The payload hash is checked in three
places too. A control enforced once is a control one bug away from being absent.

**Executing exactly once** is three cooperating pieces: an idempotency key derived from the action id
and the payload hash, a row reserved *before* the provider is called, and a `UNIQUE` constraint on
that key. If the worker dies mid-call, the reservation is already there — so on restart it asks the
provider what happened instead of retrying blind. A timeout is never treated as a failure.

---

## The tools the model can reach

Seven. That is the entire attack surface.

| Tool | Reads | Effect |
|---|---|---|
| `search_customers` | names, capped at 25 by policy | — |
| `get_customer` | one customer | — |
| `get_order` | one order, optionally items and shipment | — |
| `get_ticket` | ticket and messages (untrusted content) | — |
| `get_action_status` | lifecycle state only | — |
| `add_internal_note` | — | writes a note, author taken from the token |
| `propose_refund` | — | creates a record; **moves no money** |

No SQL tool. No shell tool. No file tool. No unrestricted HTTP tool. And no tool with a parameter
typed `object` without a schema — which is the single most common way a business-named tool turns
out to be a generic one.

Note what `propose_refund` does *not* take: no identity, no approval flag, and no payout
destination. The destination is derived server-side at execution time, so the model cannot choose
where money goes even in the request it is fully permitted to make.

---

## The test data

Two tenants that must never see each other.

```mermaid
flowchart LR
    subgraph cedar["Cedar"]
        alice["alice<br/>support_agent"]
        bob["bob<br/>support_manager"]
        fiona["fiona<br/>finance_approver"]
        dana["dana<br/>auditor"]
        co["CUS-4001 · CUS-4002<br/>CUS-4003 (restricted)"]
        oo["ORD-2001 · 2002 · 2003"]
        tt["TKT-1001<br/>10 planted injections"]
    end

    subgraph north["Northwind"]
        mallory["mallory<br/>support_agent"]
        co2["CUS-9001"]
        oo2["ORD-3001"]
        tt2["TKT-3001"]
    end

    cedar -.->|"never"| north

    style cedar fill:#1e3a5f,stroke:#4a90d9,color:#fff
    style north fill:#5f3a1e,stroke:#d9904a,color:#fff
```

Three fixtures carry most of the lessons:

- **`ORD-3001`** belongs to Northwind. Alice must never read it, however she asks, and whatever a
  ticket tells the agent to do.
- **`CUS-4003`** is marked `restricted`. An agent gets the record without `email`; a manager gets it
  with. The address is not hidden from the agent — it never reaches the agent, because policy
  returned a field list and the API dropped the rest before building the response.
- **`TKT-1001`** carries ten injection attempts written to look like ordinary customer messages:
  instruction overrides, a forged system notice claiming administrator status, a request for the
  system prompt and the connection string, calls to tools that do not exist, and a fabricated tool
  result carrying an approval.

---

## Proving it works

Nothing here is trusted because it was designed carefully. Each control has a check that fails
loudly when it stops working.

| Suite | What it proves | How to run |
|---|---|---|
| `verify_local.py` | 16 environment checks, `V-01`…`V-16` | `./scripts/verify-local.ps1` |
| `abuse_suite.py` | injection and abuse cases, `TS7-nn` | `python scripts/abuse_suite.py` |
| `action_suite.py` | approval and execution cases, `TS8-nn` | `python scripts/action_suite.py` |
| `contract_suite.py` | every call built from the published tool document | `python scripts/contract_suite.py` |
| policy tests | the Rego rules, including every deny arm | `opa test policy/` |
| API tests | token, policy client, pipeline, hashing, pagination | `pytest services/api` |

`contract_suite.py` exists because of a real failure. One tool declared an array query parameter,
Onyx serialised it one way, the API expected another, and a perfectly correct model request came
back as an error — while 219 tests passed throughout, because every one of them built its own URL.

> **A test that constructs the request is testing your assumptions, not your system.**

---

## Where to start breaking it

The fastest way to understand a control is to remove it and watch what happens. Some suggestions,
roughly in order of how much they teach:

1. **Stop OPA** and read an order you are fully entitled to read. You should get `503` and no data.
   If you get the order, something has a fallback.
2. **Point the API at the migration role** instead of `sp_api_role`. The row policies are still
   there, still correct, and now filtering nothing.
3. **Drop `FORCE`** from one table's row-level security and read across tenants.
4. **Ask the agent for fifteen customer searches** in one message. Every call will be authorised,
   allowed, correctly tenant-scoped and correctly logged — and you will have the directory.
5. **Approve a refund, then change the amount** in the database before the worker claims it. The
   hash check should refuse it twice over.
6. **Give the agent a service-account token** instead of the user's own. Then ask, as Alice, for
   `ORD-3001`.

The last one changes one header value and changes everything. That is the point of the lab.

---

## Further reading

- [`../08-local-build-runbook.md`](../08-local-build-runbook.md) — empty machine to a proven authorized read
- [`../../README.md`](../../README.md) — the write-up this system was built to support
- [`../learning/handbook.md`](../learning/handbook.md) — the field manual
- [`../runbooks/onyx-integration.md`](../runbooks/onyx-integration.md) — connecting the agent platform
- [`../../specs/`](../../specs/) — the exact contracts: schema, API, policy
