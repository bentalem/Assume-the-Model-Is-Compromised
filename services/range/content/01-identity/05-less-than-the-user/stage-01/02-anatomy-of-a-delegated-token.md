# Anatomy of a delegated token

A delegated token is an ordinary signed token with one extra claim and a narrower everything else:

```
sub:    alice                       on whose behalf
act:    { sub: status-helper }      who is actually acting        (RFC 8693)
aud:    supportpilot-api            which service only
scope:  orders:read                 only what the task needs
exp:    a few minutes               only for the task
```

`act` is the actor claim from RFC 8693, OAuth 2.0 Token Exchange. It can nest: a sub-agent acting for an agent acting for a user carries `act: { sub: sub-agent, act: { sub: status-helper } }`. Each hop must narrow, never widen. Challenge 1.8 is about that rule.

## How one is made: token exchange

The agent platform does not invent this token. It asks an issuer for it:

1. It presents the user's token (`subject_token`) and authenticates as itself.
2. It asks for a narrower `scope` and an `audience`.
3. **The issuer** checks that this agent may act for users, that the requested scope is inside the agent's registered ceiling, and that the user could do it at all.
4. The issuer mints a short, narrow token carrying `act`.

The agent can ask for less. It can never obtain more.

## How this lab makes one

This lab's issuer is a **delegation broker**, a service beside the API. It does two things:

| Endpoint | Who uses it | What it does |
|---|---|---|
| `/{profile}/v1/...` — the gateway | an agent platform registered with a profile's action document | verifies the user's token, works out the one scope this operation needs, refuses it if the profile's ceiling does not include it, mints a token for exactly that scope (60 seconds), forwards the call |
| `POST /oauth/token` — RFC 8693 exchange | an agent holding its own profile credential | the same rules, for an agent that wants a token to hold (five minutes at most, never longer than the user's own) |

A **profile** is how an agent is registered: a name and a ceiling, set by an administrator and never by the model.

| Profile | Ceiling | Never |
|---|---|---|
| `status-helper` | `orders:read` | anything that writes |
| `refund-assistant` | `orders:read`, `refunds:propose`, `actions:read` | `refunds:approve` |

The broker is also a **second issuer the API trusts**, and it has rules of its own. A broker token must carry `act`, must be ES256, and may live five minutes at most. A Keycloak token must not carry `act`. Every issuer an API trusts is a key to it, which is why the second one is deliberately narrower than the first.

## Three failures this challenge shows

| Failure | What happens | Here |
|---|---|---|
| **A broad default** | "Give it what the user has, so it works." Back to passthrough | the switch you arm |
| **A token that outlives the task** | a long expiry or a refresh token: the task ends, the authority stays | the broker mints 60 seconds per gateway call; the API refuses a broker token claiming more than five minutes |
| **`act` lost in the audit** | only `sub` is recorded, so nobody can tell a person from an agent | the agent column in the audit observation |

**Next:** how the rest of the industry does this.
