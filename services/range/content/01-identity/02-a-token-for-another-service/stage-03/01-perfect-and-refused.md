# Perfect, and refused

## What your result proves

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

Run it beside the forged token and notice that the outward result is identical:

```
token for another service   401   unauthenticated
token re-signed by attacker 401   unauthenticated
```

Same status, same code, nothing to tell them apart from outside. **One is a forgery and one is a perfectly good credential handed to the wrong door**, and the API is right to make them look the same — an error distinguishing them would tell an attacker whether they hold a real key. The distinction lives in the API's log, where an operator can see it: **specific inward, opaque outward.**

## Where the control lives

In step 5 of the verifier (`auth/tokens.py`, see 1.1's Part 1 tab): `jwt.decode` is given `audience="supportpilot-api"`, so a token whose `aud` names anything else fails there. The same check applies to both issuers the API trusts — a token from the delegation broker must name this API too.

The fixture is on the other side, in the realm file. The client `another-service` has **no audience mapper**, so its tokens are entirely legitimate and simply do not name this API. That absence is declared in the realm import rather than created by a script at run time — configuration somebody reviewed, not a side effect of running a tool.

### A real finding from this lab

Until recently the API had a gap one step further along. The JWT library checks the audience **only when the `aud` claim is present**, so a correctly signed token with **no audience at all** was accepted. Every wrong-audience test passed throughout, because each of them carried an `aud` — they tested a wrong value, never a missing one. The memory service's own test suite found it; the fix is the `require_aud` option in the same `jwt.decode` call, with a test for the missing case beside the wrong-value ones.

> A test suite that only ever sends a wrong value never learns what the code does with a missing one.

## What this check does not cover

Nothing was armed, so there is nothing to restore. It is worth knowing what the audience check does **not** stop:

- A token that really was issued for this API is accepted from whoever presents it, until it expires — 300 seconds in this realm. Stolen tokens are a transport and lifetime problem, not an audience problem.
- It protects this API only. Every other service that trusts the same identity provider needs its own audience check; one service checking does not protect its neighbours.
- One other service accepts tokens for this API's audience **on purpose**: the delegation broker (1.5 – 1.8), which is the API's gateway. That is acceptable only because the broker can turn such a token into nothing wider than it already is — a narrower token for one agent, for minutes. A service that accepted this audience and could act *more* broadly with it would be exactly the finding this challenge describes.

## Take it to a review

This is one of the few checks you can verify from outside, with no access and no cooperation beyond a token you already have:

1. Get a valid token from **any** service in their estate that uses the same identity provider.
2. Present it to the service you are reviewing.
3. If it works, the audience check is missing. Then try the same token with its `aud` claim removed, if you can get one issued that way — the missing case is a separate check.

Step 1 is usually the easy part — you are often already logged in to something.

```
<service> accepts access tokens without validating the aud claim. A token issued
for <other service> by the same identity provider was accepted as authentication.

Impact: any service in the estate that receives a user's token can act as that
user against <service>. This includes services outside this team's control, and
anything that logs or stores tokens.

Demonstrated: a token minted for <other client>, unmodified, returned <result>.

Fix: verify aud against this service's own identifier during token validation,
and require the claim to be present.
```

The "Impact" paragraph is what moves it. A missing audience check reads like a configuration nit until somebody counts how many services are in the blast radius — and the answer is *all of them that trust the same issuer*.

> **The signature check answers "did we issue this?". The audience check answers "did we issue it to you?".** A system that only asks the first question has one credential domain, however many services it thinks it has.
