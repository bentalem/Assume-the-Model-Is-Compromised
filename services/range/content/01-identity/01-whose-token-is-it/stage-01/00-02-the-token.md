# Part 1: the token

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
