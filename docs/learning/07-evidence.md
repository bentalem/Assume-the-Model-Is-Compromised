# Evidence and audit: the system behind track 7

This is the same architecture lesson shown in challenge 7.1's two opening Learn tabs. Read it before starting track 7. No terminal is needed for the challenges.

## 1. Start here: where the evidence comes from

Read these two architecture tabs before you start challenge 1 of track 7. Every challenge in this track reads the same table, and each one goes wrong in a different way if you do not know who writes to it, what they write, and what they leave out.

Tracks 1–6 asked whether a control refused something. Track 7 asks a different question: **afterwards, how would anyone know?** The answer in this system is one table, `app.audit_events`, and nothing else. There is no report, no ticket, and no transcript that counts as evidence.

## The architecture

```text
SupportPilot API ──── every decision, allowed or denied ───────┐
   (reads, denials, proposals, approvals)                      │
                                                               v
Worker ────────────── every execution, succeeded or refused ─> app.audit_events
   (the only thing that moves money)                           ^
                                                               │
The Range ─────────── every arm, restore and reset ────────────┘
   (through one fixed function, never directly)

                   read by: sp_auditor_role (no service logs in as it)
                            the Range's observations (fixed functions)
```

Three writers, and each one writes **its own INSERT statement**, with its own list of columns. That detail decides what the trail can answer, and it is the first thing challenge 7.1 asks you to check.

## Who may do what to the table

| Role | Insert | Read | Update / delete |
|---|---|---|---|
| `sp_api_role` | yes, only for its current tenant or no tenant | **no** | no |
| `sp_worker_role` | yes | no | no |
| `sp_range_role` | only through `range.record_event()`, which fixes the actor | only through fixed observation functions | no |
| `sp_auditor_role` | no | yes | no |
| `sp_migrator_role` (owner) | yes | yes | holds the grant — and no policy lets it match a row |

Two things in that table are deliberate and easy to miss:

- **The API cannot read what it wrote.** An API that could read the trail would be one bug away from returning it to a caller.
- **Nothing that runs holds `UPDATE` or `DELETE`.** The trail is append-only by grant, and `FORCE ROW LEVEL SECURITY` applies the table's policies to the owner as well. Challenge 7.1 asks you to check this rather than believe it.

## Two ways an event is written

The API has two paths into the table, and they fail differently:

| Path | Used for | If the audit write fails |
|---|---|---|
| `record_in` — inside the caller's transaction | proposals, approvals, notes: anything with an effect | **the effect rolls back.** No evidence, no effect (rule 9) |
| `record` — its own transaction | denials and completed reads | logged loudly as `audit_write_failed`; **the denial still stands** |

The second path is not a gap in rule 9. A denial changes nothing, so there is nothing to roll back — and turning an audit outage into a `500` would hand the caller a different answer from the one the policy gave.

The worker writes its execution event in the same transaction as the execution result, the job state and the request state. An execution is never visible without the row that records it.

## What is real in this lab?

All of it. Every row you read in this track was written by the same code paths that write it outside the lab. The Range reads the table through fixed, read-only functions; it cannot insert a row that claims to be the API or the worker.

The Range's own actions are in there too, as `actor_type = 'range'`. When you look for a request in the trail, you will find your own arming next to it. That is on purpose: the service with the most authority in the lab is also the one whose actions are hardest to miss.

**Next:** what one row records, and which writer fills which column.

## 2. What one row records

An audit row is a record of **one decision about one thing, made by one actor**. It is not a log line and it is not a transcript: it never holds a payload body, a response, or a credential — only identifiers, decisions and hashes.

## The columns, and who fills them

The table declares eighteen columns. Two are filled by the database (`event_id`, `occurred_at`). The rest depend on which writer made the row:

| Column | What it answers | API | Worker | Range |
|---|---|---|---|---|
| `request_id` | which request produced this row | the API request | `worker-<job id>` | the Range request |
| `actor_type` | what kind of actor | `user` | `workload` | `range` |
| `actor_id` | which actor | a user uuid | the worker's id | `range-service` |
| `organization_id` | which tenant | the resource's tenant, or empty | the request's tenant | empty |
| `action` | what was attempted | `order.read`, `refund.propose`… | `refund.execute` | `range.arm`, `range.restore`, `range.reset` |
| `resource_type`, `resource_id` | on what | the trusted resource | `action_request` and its id | `mutation` and its id |
| `decision` | what was decided | `allowed`, `denied`, `succeeded`, `approved`, `rejected` | `succeeded`, `failed` | `allowed`, `succeeded`, `failed` |
| `reason` | why | a reason code | an outcome or refusal code | a short code of its own |
| `policy_version` | under which rules | when the policy answered | **never** | never |
| `payload_hash` | exactly what content | proposals and approvals | every execution | never |
| `result_reference` | what it created or touched outside | e.g. the new action id | the provider's reference | never |
| `agent_id` | which agent acted for the human | the delegation chain, for a broker token (track 1, 1.5 - 1.8); empty for a user's own | not in the statement | not in the statement |
| `trace_id` | — | in the statement, always empty | not in the statement | not in the statement |
| `previous_event_hash`, `event_hash` | — | **not in any statement** | not in any statement | not in any statement |

Read the last three rows twice. A declared column is a statement of intent, not evidence that anything fills it. Challenge 7.1 asks you to count.

## `decision` is a small vocabulary; `reason` is where the meaning is

The `decision` column is constrained to six words. The reason column is not, and it is the one that tells you **which layer acted**:

| Where the reason comes from | Examples | `policy_version` |
|---|---|---|
| the API, before policy is asked | `unknown_subject`, `resource_not_visible` | empty |
| the policy client, when the engine gives no usable answer | `policy_unavailable`, `policy_malformed` | empty |
| the policy itself | `same_organization_and_allowed_role`, `not_a_member_of_resource_organization`, `amount_exceeds_role_limit`, `default_deny` | `2026-09-28.1` |
| the propose and approve steps | `action_pending_approval`, `independent_approval_recorded` | from the policy decision |
| the worker's refusals | `no_approval_decision`, `self_approval_detected`, `approval_expired`, `payload_hash_mismatch_stored`… | empty |

Two readings follow from that table, and both come up in this track:

- **A denial with no policy version was not refused by policy.** It was refused before policy was asked, or the engine gave no usable answer.
- **In this trail, `failed` does not mean nothing decided.** The worker records its own refusals as `failed`, with the refusal code as the reason. The decision word tells you the outcome; only the reason tells you whether a control acted.

## One action, several requests

A refund is not one request. It is four, made by three actors:

```text
refund.propose        user (the requester)   request 1   result_reference = the action id
refund.approve.view   user (the approver)    request 2   resource_id      = the action id
refund.approve        user (the approver)    request 3   resource_id      = the action id
refund.execute        workload (the worker)  worker-…    resource_id      = the action id
```

Grouping by `request_id` gives you four unrelated rows. What joins them is the **action id**: written as `result_reference` on the proposal, and carried as the resource on every step after it. The `payload_hash` on propose, approve and execute is what tells you the approved content is the executed content.

## Where the track goes

| Challenge | What you read | What it teaches |
|---|---|---|
| 7.1 | one completed refund, the column census, the write grants | how to reconstruct an action, and what the trail cannot prove |
| 7.2 | one request, as the response and as the row | why a response is not evidence, and what to ask for instead |
| 7.3 | two refusals, one with a row and one without | prevented versus merely failed |
| 7.4 | a passing test and its name | what a green test proves |

Nothing in this track arms a control except 7.2, and that only to produce a failure worth reading.
