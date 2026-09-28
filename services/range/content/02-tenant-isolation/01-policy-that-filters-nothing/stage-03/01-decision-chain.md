# The decision chain

## What your result proves

What the database asked, in order, and the step that answered wrongly.

When the control held:

```
SELECT ... FROM app.orders            cedar context set
  │
  ├─ row security enabled?            yes
  ├─ role bypasses it?                no    NOBYPASSRLS, NOSUPERUSER
  ├─ owner, with FORCE off?           no    FORCE is on
  └─ apply policy
       organization_id = app.current_org()
       → cedar rows only
```

When you armed it:

```
SELECT ... FROM app.orders            the same statement, the same context
  │
  ├─ row security enabled?            yes            ← unchanged
  ├─ role bypasses it?                no             ← unchanged
  ├─ owner, with FORCE off?           YES
  │                                      │
  │                                      └─ return every row
  └─ policy never consulted
```

**The policy did not fail. It was never asked.**

That distinction is the whole lesson, and it is the reason this failure survives review: there is no broken component to find. Every part you would inspect is working correctly, including the policy, and the answer is still wrong.

## Where the control lives

Two lines of migration `0003`, per table: `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`. The policy under them reads `app.current_org()`, which the API sets transaction-locally on every request (`db.py`).

The input that decided your result was none of those. It was **who owns the table**:

| Step | Where the answer lives | Who sees it in a review |
|---|---|---|
| enabled? | the migration | anyone reading the schema |
| bypasses? | `pg_roles` | nobody, unless asked |
| owns it? | **the connection string, and the migration history** | **nobody** |
| the policy | the migration | everyone — and it is fine |

Two of the four inputs are invisible to the review everyone actually performs — and they are the two that decide whether the other two do anything.

In this lab the owner is `sp_migrator_role` and the API connects as `sp_api_role`, so the API's own reads stayed filtered even while you had `FORCE` off. The observation read the table **as its owner** to show what a system that connects as the owner would have returned.

## What restoring fixes

Restoring puts `FORCE` (or row security) back, and the owner's next read is filtered again. Nothing is left behind in the table.

What restoring cannot tell you is **who read what while it was off**. The reads in this challenge were made as the table's owner, directly in the database — the path the application does not take — and the audit trail is written by the API, so nothing recorded them.

Worth knowing for track 7: had a cross-tenant read gone through the API, the refusal would have been recorded as:

```
order.read   denied   resource_not_visible   policy_version: (none)
```

No policy version, **and that is the information**: the request was refused before policy was ever asked, because the caller could not see that the record existed. A refusal from policy reads `not_a_member_of_resource_organization` and carries a version. From outside, both are an identical 404. Inside, they are different systems — and only the reason code tells you which one acted.

## Take it to a review

The next tab is the review itself: two queries to ask a DBA for, the reassuring non-answers you will hear, and how to write the finding.
