# Identity and tokens: the system behind track 1

This is the same architecture lesson shown in challenge 1.1's four opening Learn tabs. Read it before starting track 1. No terminal is needed for the challenges.

## 1. Start here: how identity works in this system

Read these four architecture tabs before you start challenge 1.1. They explain the system you will test throughout track 1: who issues a credential, what the API checks, and where the answer to "what may this person do?" really comes from.

Every request to the SupportPilot API has to answer three questions, in this order:

| Question | Name | Who answers it here |
|---|---|---|
| Is this credential real? | **Authentication** | the API, by checking the token's signature and claims |
| Who does it name? | **Identification** | the token's `sub` claim |
| What may this person do, right now? | **Authorization attributes** | **the core database**, on every request |

The first two are the token's job. The third is not, and track 1 is about keeping it that way.

The second half of the track (1.5 to 1.8) adds one refinement. A token minted **for an agent** also
carries a *limit*: which agent is acting, and the narrow scope it was given. A limit can only take
authority away. The third question is still answered by the database.

## The architecture

```text
Signed-in user
    |
    | signs in
    v
Keycloak (identity provider)  ---- issues a signed access token
    |
    v
Agent runtime (Onyx, or the lab's probe)
    |
    | Authorization: Bearer <token>
    v
SupportPilot API
    |---- 1. verify the token             (auth/tokens.py)
    |---- 2. load the person              (core PostgreSQL: users, memberships)
    |---- 3. load the record asked for    (only in tenants the person belongs to)
    |---- 4. ask the policy               (OPA)
    +---- 5. query, trim fields, audit
```

From 1.5 on, a second path sits beside the first:

```text
Agent (a registered profile) ---- the user's token ----> Delegation broker
                                                             |
                                    mints a token: sub = the user, act = the agent,
                                    scope = only what this call needs, 5 minutes at most
                                                             v
                                                      SupportPilot API   (same five steps)
```

**Keycloak** issues the token. It is the only component that can sign a user's own token. (A second issuer, the delegation broker, signs narrower tokens for agents; that is challenges 1.5 to 1.8.) **The API** verifies the token and then treats it as a name only. **The core database** holds who belongs to which organisation, with which role — and that is what every decision is made from.

## Who is allowed to do what?

| Component | Can | Cannot |
|---|---|---|
| Keycloak | sign tokens for users who log in | decide what a user may read in SupportPilot |
| The delegation broker (1.5 – 1.8) | sign narrower tokens naming the user and an agent | mint more than the agent's ceiling, or `refunds:approve` for anyone |
| The agent runtime | carry the user's token, or a delegated one, to the API | change what is inside a token |
| The model | choose which tool to call and with what arguments | set a user, a tenant or a role — no tool has such a field |
| The API | verify, load the person, ask the policy | accept a tenant or role from the request, or treat a token's scope as a grant |
| The core database | say which memberships are active now | — it is the source of truth |

## What is real in this lab?

The Keycloak realm, the API's verifier, the database and the policy are the real ones. The Range's **probe** logs in as the seeded users with their lab passwords and sends real requests with real tokens. It never builds a request the API would not also receive from Onyx.

Two fixtures exist only to be tested:

- `agent-service` — a Keycloak user standing in for an agent's own account. By default it has **no membership anywhere**, so it can log in and reach nothing.
- `another-service` — a second client in the same realm whose tokens name **no** SupportPilot audience.

From 1.5 on, two **agent profiles** are registered with the delegation broker: `status-helper`, which may only read orders, and `refund-assistant`, which may read orders, propose refunds and read their status. They are not users and have no row in the database; they appear in a token's `act` claim and in the audit trail beside the person they act for. The broker runs under its own compose profile, `delegation`.

**Next:** what is inside a token, and what the API checks before it believes one.

## 2. Part 1: the token

An **access token** is a short text string in three parts: a header, a set of claims, and a signature. Keycloak signs it with a private key. Anyone can read the claims; only Keycloak can produce a valid signature over them.

## What is inside one

| Part | Field | What it says | Example here |
|---|---|---|---|
| Header | `alg` | which algorithm signed it | `RS256` |
| Header | `kid` | which of Keycloak's keys signed it | a key id from the realm |
| Claim | `iss` | who issued it | the `supportpilot` realm |
| Claim | `aud` | which service it is **for** | `supportpilot-api` |
| Claim | `sub` | which person it names | `alice-id` |
| Claim | `exp`, `iat` | when it expires, when it was issued | five minutes apart in this realm |
| Claim | `typ` | what kind of token it is | `Bearer` |

A token is a **snapshot taken at login**. Whatever it says stays true for its whole lifetime, even if the world changes. This realm issues access tokens that live **300 seconds**.

## Which clients can get one

A **client** is an application registered in Keycloak. Only some clients mint tokens, and each decides which audience its tokens carry.

| Client | Mints tokens? | Audience it adds |
|---|---|---|
| `onyx-web` | yes, when a user signs in to Onyx | `supportpilot-api`, `supportpilot-memory` |
| `supportpilot-test-harness` | yes, for the lab's scripts and probe | `supportpilot-api`, `supportpilot-memory` |
| `another-service` | yes | **none** — the fixture for 1.2 |
| `supportpilot-api` | no, it only receives tokens | — |
| `supportpilot-memory` | no, it only receives tokens | — |

Keycloak is not the only issuer the API trusts. From 1.5 on, the **delegation broker** signs tokens too: never for a user on their own, only for an agent acting for one. Its tokens always carry `act`, use ES256, and live five minutes at most.

## What the API checks, in order

The verifier in `services/api/src/supportpilot_api/auth/tokens.py` runs these checks in this order. The first one that fails ends the request.

1. **Shape:** three parts separated by dots.
2. **Issuer:** the `iss` the token names chooses which trusted issuer's rules apply, before any key is fetched. An issuer the API does not trust is refused. For every token in challenges 1.1 to 1.4, that issuer is Keycloak.
3. **Algorithm:** `alg` must be on a fixed list — `RS256`, `RS384`, `RS512`, `ES256`, `ES384`. The token does not get to choose. `none` and `HS256` fail here.
4. **Key:** `kid` must name a key the chosen issuer publishes — Keycloak's, or for a delegated token the broker's. A delegated token must also be ES256.
5. **Signature and claims:** the signature must verify, `iss` must be the chosen issuer, `aud` must be present **and** name `supportpilot-api`, and `exp`, `iat` and `nbf` must be valid.
6. **Subject:** `sub` must be present.
7. **Type:** a refresh token or an ID token is refused.
8. **Actor:** a user's own token must not carry an `act` claim. A delegated token must carry one that names a registered agent, and may not claim a life longer than five minutes. Challenge 1.5 is about why.

Every failure gives the caller the same answer: `401 unauthenticated`. The reason goes only to the API's log, where an operator can read it and an attacker cannot.

## What the token is *not* used for

From a user's own token, the API reads exactly one thing to decide anything: `sub`, the person's identity. It does not read a role, a tenant or an organisation from it, even if the token contains one. Those come from the database — the next tab.

From a delegated token (1.5 to 1.8) it reads two more things, and both are **limits**: `act`, the agent acting for that person, which goes into the audit trail beside them; and `scope`, which the policy uses to refuse whatever the token does not cover. Neither can add a permission the person does not already have in the database.

**Read the code:** `services/api/src/supportpilot_api/auth/tokens.py` and the clients in `infrastructure/local/keycloak/supportpilot-realm.json`.

## 3. Part 2: from a token to a person

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

## 4. Part 3: from a person to a decision

The API now knows who is asking and where they belong. It still does not know **which tenant this request is about**. That comes from the record being asked for, not from the person and not from the request.

## The exact order

For a request such as `GET /v1/orders/ORD-2001`:

1. **Verify the token** and read `sub` (Part 1).
2. **Load the person** and their active memberships (Part 2).
3. **Load the record.** The order number is looked up **once per tenant the person belongs to**, each time inside that tenant's own database context, so row-level security applies to every lookup. A tenant the person does not belong to is never queried at all.
4. **If nothing was found**, the answer is `404` — the same answer whether the order does not exist or belongs to another tenant. The audit row records `resource_not_visible`.
5. **Ask the policy.** The input includes the person's roles **in the record's tenant** — not their roles anywhere else. For a delegated token it also includes the agent and the token's scope, and the policy refuses anything the scope does not cover (1.6).
6. **Query and trim.** The policy can allow the read and still remove fields. A support agent reading a restricted customer gets fewer fields than a manager does.
7. **Write the audit row.** It names the person loaded in step 2 as the actor, and — for a delegated token — the agent chain beside them in `agent_id`.

Example of what alice's two reads look like from the inside:

```text
alice -> ORD-2001   her tenants: cedar   found in cedar       -> policy asked -> 200
alice -> ORD-3001   her tenants: cedar   not found in cedar   -> 404, policy never asked
```

Northwind was not searched in the second request. There was nothing for alice to learn about it, not even whether ORD-3001 exists.

## What this means for an agent

The model sees none of these steps. It sees tools such as `get_order`, whose inputs are an order number and two yes-or-no options. It has no field in which to name a user, a tenant or a role — so the most it can do is ask for a record, and everything above decides what that request is worth.

That makes the **credential on the call** the single most important choice in the system. Whatever identity the token names is the identity every step above works for — and, from 1.5 on, whatever limit the token carries is the most of that identity the agent can use.

## Which challenge tests each part?

| Challenge | The question you will answer |
|---|---|
| 1.1 | What changes when the agent carries its own credential instead of the user's? |
| 1.2 | Does the API accept a genuine token that was issued to a different service? |
| 1.3 | When a role is removed in the database, how soon does the API stop honouring it? |
| 1.4 | What does a forged or rewritten token achieve, and where is it stopped? |
| 1.5 | How much of the user's authority does the agent need — and who can tell afterwards that it acted? |
| 1.6 | A token narrowed correctly: does anything read the narrowing? |
| 1.7 | Who decides an agent's scope — and what is left when the agent does? |
| 1.8 | When an agent hands its token on, can the chain grow? |

**Now start challenge 1.1.** You will send the same two requests with two different credentials and compare every row.
