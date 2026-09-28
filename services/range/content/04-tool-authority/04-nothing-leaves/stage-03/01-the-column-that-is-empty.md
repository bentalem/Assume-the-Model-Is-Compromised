# The column that is empty

## What your result proves

Seven operations. Five reads and two writes, and both writes land in this system's own database.

| Operation | Method | What the effect touches |
|---|---|---|
| `get_order` | GET | reads |
| `search_customers` | GET | reads |
| `get_customer` | GET | reads |
| `get_ticket` | GET | reads |
| `get_action_status` | GET | reads |
| `add_internal_note` | POST | inserts a row in `app.internal_notes` |
| `propose_refund` | POST | inserts a pending action request; the response documents `state` as `Always PENDING_APPROVAL: no money has moved` |

Twelve parameters and seven body fields between them. Not one names a destination: no address, no URL, no channel, no recipient outside the tenant, no webhook. Both bodies set `additionalProperties: false`, so a destination cannot be smuggled in as an extra field either — it comes back as a rejected request. The right-hand column of the composition table is empty.

Say the narrow thing, not the big one:

| Claim | Status |
|---|---|
| "This system cannot make an outbound connection" | false, and easy to disprove |
| "Nothing here reaches the network" | false |
| "No registered operation carries a destination, and none delivers content outside this system" | true, and you just checked it |

The API makes outbound HTTP on nearly every request: it calls OPA for a decision, and it fetches signing keys from the identity provider to verify a token. Neither is a tool, and neither carries a byte the model chose.

> **An absence is only evidence when you say precisely which absence.** "Nothing leaves" invites one counter-example and you lose the room.

## Where the control lives

One component here genuinely is built to reach outside: `SandboxRefundAdapter` in the worker. Every property of it is a different kind of control.

| Property | Where it lives | Kind |
|---|---|---|
| Host must be in an allowlist | `__init__`, raises on construction | code |
| Which hosts are on that list | passed in by the caller | configuration |
| Destination is not in the payload | the refund body has no destination field | schema |
| Reached only after an approval | propose, approve, execute | architecture |

The first row is the one to take away. The check is in the constructor: an adapter pointed somewhere it should not be must not exist at all. Compare that with validating the destination inside `execute`, where the object is already built and injected — and where one caller can skip the check.

Two more facts, because a reviewer who stops at "there is an allowlist" has stopped one step early. `execute` raises `NotImplementedError`: no provider has been chosen. And the worker constructs `FakeRefundAdapter`, which applies refunds to a dictionary in memory. So today, in this compose project, even the refund does not leave.

Between the model and that adapter: the model can call `propose_refund`, which writes a request in `PENDING_APPROVAL`. An independent approver approves a payload hash. The worker recomputes the hash before executing and refuses on a mismatch. The model is on the near side of all three.

## What this check does not cover

The day somebody adds `send_customer_email`, some of this lab's controls would extend to it:

| Control | Covers |
|---|---|
| An identifier parameter with a pattern, resolved server-side | the recipient is a customer of this tenant, never a typed address |
| API membership check plus row-level security | the recipient row is not in another organisation |
| `extra="forbid"` on the body | no destination field arrives that the schema did not declare |
| Propose, approve, execute | rule 8 already names irreversible effects, and a sent message is one |
| Audit in the same transaction as the state change | there is a row saying a message went to `CUS-4002` |
| Adding to the approved operation list | a human reads a diff before the tool exists |

And three things nothing in a per-call model could hold — not oversights:

1. **A relation between the body and what the session read.** The policy input has four keys, and a fifth for a delegated token, and the body is not one of them. A rule cannot compare things it is not given.
2. **A ceiling across calls.** For a read that means volume. For a send it means every message is individually fine.
3. **Evidence of what was actually sent.** Look at what the note write records: the actor, the organisation, the action, the policy version and `result_reference` — the note's id. Not the note: rule 11 keeps content out of the trail. For a note that is fine, because the row is still in `app.internal_notes`. **A sent message has no such row unless somebody decided to create one**, and a trail that proves a message went to `CUS-4002` at 14:02 cannot tell you what was in it — the one question an incident asks.

> **For a read, minimisation and evidence agree. For a send, they conflict, and somebody has to choose in writing.**

## Take it to a review

1. **Draw the two columns.** Every tool that puts data into the context on the left, every tool that takes data out on the right. Then read the pairs, never the rows.
2. **For each tool on the right: who chooses the recipient, and who chooses the content?** If the answer to the second is "the model", say so in those words.
3. **What is the authorization input for a send?** Ask to see it. If the body is not in it, no policy rule can be written about the body, and that is a structural limit rather than a backlog item.
4. **What does the audit row for a send contain?** If it does not contain the content, ask where the content is recoverable from, and for how long.
5. **What is the ceiling on sends per session, and what enforces it?** A number in a prompt is not an answer.
6. **Is the effect reversible?** If not, ask which of propose, approve and execute exists, and who is allowed to be both the proposer and the approver.

Question 1 is the whole method and it takes ten minutes. Question 4 is the one that is almost never answered on the day you ask it.
