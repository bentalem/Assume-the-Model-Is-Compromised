# What the trail said

**Request A was prevented.** `order.read` on `ORD-3001`, `denied`, reason `resource_not_visible`.

**Request B merely failed.** There is no row for it, anywhere.

## Why B left nothing behind

Look at the source panel for the validation handler. When a request body does not match the schema,
the API logs a line and returns `400 invalid_request` — and that is all it does.

It cannot write an audit row, and not because somebody forgot. At that moment there is **no subject**
(the request has not been through the pipeline), **no resource** (nothing was loaded), and **no
decision** (nothing was asked). An audit row is a record of a decision, and no decision was made.

So the absence is not a logging gap. It is the correct behaviour of a system where nothing happened.

> **A request that is not in the audit trail usually never reached the thing that writes to it.**

## And a well-formed B would have succeeded

This is the part that makes the distinction matter rather than being a technicality.

Alice is a support agent in cedar. `ORD-2001` is cedar's, and it is in a refundable state. The
amount was inside her role's limit. Everything about that request was permitted — the only thing
wrong with it was a string where an enumeration was expected.

Send it again with `damaged_on_arrival` and it creates a refund proposal.

A report that said *"the system blocked a refund proposal"* would have been wrong in the way that
takes about ninety seconds for an engineer to disprove, and would have taken the rest of the report
down with it.

## Now read A's row again

```
order.read   denied   resource_not_visible   policy_version: (none)
```

**No policy version.** That is not missing data; it is the finding.

The request was refused by the **resource lookup**, before policy was ever consulted. Alice could not
see that `ORD-3001` existed, so there was nothing for the business rules to have an opinion about.

Had policy refused it, the row would read `not_a_member_of_resource_organization` and carry
`2026-09-07.1`. From outside, both are an identical 404. Inside they are different layers — and the
reason code is the only thing that distinguishes them.

This matters when a control changes. If someone edits the policy and you want to know whether
cross-tenant reads are still refused, a trail full of `resource_not_visible` tells you the policy was
never the thing refusing them, so the policy change was not the risk you thought it was.

## How to write it

```
Confirmed: cross-tenant order reads are refused, at the resource lookup, before the
policy engine is consulted. Evidence: audit rows for ORD-3001 recording
order.read / denied / resource_not_visible, with no policy version.

Not tested: refund proposal authorization. The attempt made during testing was
rejected by schema validation (400, no audit row) and never reached the
authorization pipeline. A well-formed request would have been permitted.
```

The second paragraph is what separates a report people trust from one they check. **Saying what you
did not establish is not a weakness in a finding; it is the thing that makes the rest of it
credible.**

## The habit

Whenever something does not happen, before you write it down:

> **Establish whether it was prevented or whether it merely failed.** Look for the decision row. If
> there is none, you have not tested the control — you have tested your request.
