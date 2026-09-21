# The decision chain

What the database asked, in order, and the step that answered wrongly.

## When the control held

```
SELECT ... FROM app.orders            cedar context set
  │
  ├─ row security enabled?            yes
  ├─ role bypasses it?                no    sp_api_role: NOBYPASSRLS, NOSUPERUSER
  ├─ role owns the table?             no    owner is sp_migrator_role
  └─ apply policy
       organization_id = app.current_org()
       → cedar rows only
```

Nothing dramatic happened. The query was rewritten and northwind's row was never a candidate.

## When you armed it

```
SELECT ... FROM app.orders            the same statement, the same context
  │
  ├─ row security enabled?            yes            ← unchanged
  ├─ role bypasses it?                no             ← unchanged
  ├─ role owns the table?             YES, and FORCE is off
  │                                      │
  │                                      └─ return every row
  └─ policy never consulted
```

**The policy did not fail. It was never asked.**

That distinction is the whole lesson, and it is the reason this failure survives review: there is no
broken component to find. Every part you would inspect is working correctly, including the policy,
and the answer is still wrong.

## What each step corresponds to in a real system

| Step | Where the answer lives | Who sees it in a review |
|---|---|---|
| enabled? | the migration | anyone reading the schema |
| bypasses? | `pg_roles` | nobody, unless asked |
| owns it? | **the connection string, and the migration history** | **nobody** |
| the policy | the migration | everyone — and it is fine |

Two of the four inputs are invisible to the review everyone actually performs — and they are the
two that decide whether the other two do anything. The policy gets read by everybody; ownership gets
read by nobody.

## The reason code, if this had gone through the API

Worth knowing for track 7. In this lab a cross-tenant read that the resource lookup refuses is
recorded as:

```
order.read   denied   resource_not_visible   policy_version: (none)
```

No policy version, **and that is the information**: the request was refused before policy was ever
asked, because the caller could not see that the record existed. A refusal from policy reads
`not_a_member_of_resource_organization` and carries a version.

From outside, both are an identical 404. Inside, they are different systems — and only the reason
code tells you which one acted.
