# Start here: where the evidence comes from

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
