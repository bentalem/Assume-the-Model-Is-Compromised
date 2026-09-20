# Perfect, and refused

`aud`.

Everything else about that token was correct:

| | |
|---|---|
| Signature | valid, signed by the realm's key |
| Issuer | the same issuer the API trusts |
| Subject | alice — a real user, with real memberships |
| Expiry | well within its window |
| Algorithm | RS256, as configured |
| **Audience** | **does not name this API** |

Six of seven, and the seventh is the one that decided.

## The contrast is the point

Run it beside the re-signed token from 1.4 and notice that the outward result is identical:

```
token for another service   401   unauthenticated
token re-signed by attacker 401   unauthenticated
```

Same status, same code, nothing to tell them apart from outside. **One is a forgery and one is a
perfectly good credential handed to the wrong door**, and the API is right to make them look the
same — an error distinguishing them would tell an attacker whether they hold a real key.

The distinction lives in the logs, where an operator can see it. Same shape as the 404 in 7.3 and
the opaque validation error in 6.1: **specific inward, opaque outward.**

## What the fixture actually is

The realm has a second client, `another-service`, and the interesting thing about it is what it does
*not* have: **no audience mapper.** Its tokens are entirely legitimate; they simply do not name the
SupportPilot API.

That absence is the whole fixture, and it is declared in the realm file rather than created at
runtime by a script — so it is configuration somebody reviewed, not a side effect of running a tool.

## How to test this on somebody else's system

This is one of the few checks you can verify from outside with no access and no cooperation beyond a
token you already have:

1. Get a valid token from **any** service in their estate that uses the same identity provider.
2. Present it to the service you are reviewing.
3. If it works, the audience check is missing.

Step 1 is usually the easy part — you are often already logged in to something.

## Writing it up

```
<service> accepts access tokens without validating the aud claim. A token issued
for <other service> by the same identity provider was accepted as authentication.

Impact: any service in the estate that receives a user's token can act as that
user against <service>. This includes services outside this team's control, and
anything that logs or stores tokens.

Demonstrated: a token minted for <other client>, unmodified, returned <result>.

Fix: verify aud against this service's own identifier during token validation.
```

The second paragraph is what moves it. A missing audience check reads like a configuration nit until
somebody counts how many services are in the blast radius — and the answer is *all of them that
trust the same issuer*.

> **The signature check answers "did we issue this?". The audience check answers "did we issue it to
> you?".** A system that only asks the first question has one credential domain, however many
> services it thinks it has.
