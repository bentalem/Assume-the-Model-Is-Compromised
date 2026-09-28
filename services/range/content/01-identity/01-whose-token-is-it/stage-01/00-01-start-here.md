# Start here: how identity works in this system

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
