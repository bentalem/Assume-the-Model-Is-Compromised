# Part 1: the question and the answer

## The question: the policy input

For every tool call, the API sends OPA one JSON document with four parts. Everything in it comes from the verified token or from a server-side lookup — nothing comes from the model's arguments.

| Part | Contains | Comes from |
|---|---|---|
| `subject` | the person's id, their organisations, their roles **in the record's tenant**, their authentication level | the token's `sub`, then `app.memberships` (track 1) |
| `action` | one of eight fixed names | the route that was called |
| `resource` | the record's tenant, type, id, and attributes such as `sensitivity` or `requester_id` | the database, loaded **before** the question is asked (track 2) |
| `context` | the request id, the time, the network zone | the API itself |

The eight actions: `order.read`, `customer.read`, `customer.search`, `ticket.read`, `note.create`, `refund.propose`, `refund.approve` and `action.read`.

## The answer: the decision

The rules return one document, and the API accepts it only if every part has the right type:

| Field | Meaning | Example |
|---|---|---|
| `allow` | exactly `true` or `false` — not `"true"`, not `1` | `true` |
| `reason` | why, as a stable code | `same_organization_and_allowed_role` |
| `policy_version` | which version of the rules decided | `2026-09-28.1` |
| `obligations` | conditions attached to an allow | `{"allowed_fields": [...]}` |

Two obligations exist in this lab:

- **`allowed_fields`** — "yes, and only these fields". The API removes every other field between the query and the response. Challenge 3.2.
- **`max_results`** — a page-size cap on searches, which the API applies to the query. Challenge 4.1.

## Deny by default, written down

The first rule in the file is not an allow. It is the answer when nothing else matches:

```rego
default decision := {
    "allow": false,
    "reason": "default_deny",
    "policy_version": "2026-09-28.1",
}
```

Every allow below it has to state its own reason. A deny carries a reason and the policy version too, and both end up in the audit row — so every refusal the rules make can be traced to the exact rules that made it.

## What the API does with the answer

| The decision | Audit row | The caller gets |
|---|---|---|
| allow | `allowed`, the reason, the policy version | the data — minus any field not in `allowed_fields` |
| deny from the rules | `denied`, the reason, the policy version | `404`, the same as for a record that does not exist |

`404` rather than `403` is deliberate: a refusal must never confirm that a record exists in another tenant.

**Read the code:** `policy/supportpilot/authz.rego`, `services/api/src/supportpilot_api/pipeline.py`.
