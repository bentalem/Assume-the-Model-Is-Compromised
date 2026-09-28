# Part 2: from a token to a person

A verified token gives the API one fact: the `sub` of the person it names. Everything else — which organisations they belong to and in which role — is looked up in the core PostgreSQL database, **on every request**.

## Where is it stored?

Three tables in the `app` schema of the core database:

| Table | One row represents | Main fields |
|---|---|---|
| `app.users` | one person the API knows | `id`, `identity_subject` (the Keycloak `sub`), `display_name`, `status` |
| `app.organizations` | one tenant | `id`, `slug` (`cedar`, `northwind`), `status` |
| `app.memberships` | one person's role in one tenant | `user_id`, `organization_id`, `role`, `status` (`active` or `revoked`) |

A person can have memberships in more than one organisation. Nobody in the seed data does — except the service account, once you configure it in 1.1.

## The people in this lab

| Keycloak `sub` | Organisation | Role |
|---|---|---|
| `alice-id` | cedar | `support_agent` |
| `bob-id` | cedar | `support_manager` |
| `fiona-id` | cedar | `finance_approver` |
| `dana-id` | cedar | `auditor` |
| `mallory-id` | northwind | `support_agent` |
| `agent-service-id` | **none** | — until 1.1's control grants one in every tenant |

The agents in 1.5 to 1.8 — `status-helper` and `refund-assistant` — are not in this table, and not in the database. A delegated token names alice as `sub`, so it is alice who is loaded here, with alice's roles; the agent only narrows what those roles are used for.

## How the person is loaded

1. The route receives the request. `request_scope` in `dependencies.py` takes the `Authorization` header.
2. The verifier checks the token (the previous tab) and returns its `sub`.
3. `load_subject` calls the database function `app.resolve_subject(sub)`. It returns the person and every **active** membership in an **active** organisation.
4. The API builds a `Subject`: the person, and a map from each organisation to their roles in it.

There is no cache. The next request repeats steps 2 to 4, so a change to `app.memberships` counts from the very next request — which is exactly what challenge 1.3 measures.

Why a function and not a plain query? Row-level security on these tables shows a caller only their own rows, keyed on their internal user id — but at this moment the API holds only the Keycloak `sub`. The id is exactly what it is trying to find. The migration calls this a chicken-and-egg problem. `app.resolve_subject` is a narrow `SECURITY DEFINER` function that answers exactly one question — "who is this `sub`, and where do they belong?" — and nothing else.

## Two situations worth telling apart

| Situation | What the API does |
|---|---|
| Token valid, but no user with that `sub` | authenticated, unknown here — the request is refused as not found |
| User exists, but no active membership | authenticated, known, and allowed **nothing** |

That second case is the `agent-service` account before you arm 1.1: a perfectly valid login that can reach nothing, because it belongs nowhere.

**Read the code:** `services/api/src/supportpilot_api/dependencies.py`, `repositories/memberships.py` and `database/migrations/0002_core_tenancy.sql`.
