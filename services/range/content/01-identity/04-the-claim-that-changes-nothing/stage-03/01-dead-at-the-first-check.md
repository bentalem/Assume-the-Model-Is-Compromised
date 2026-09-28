# Dead at the first check

## What your result proves

`unauthenticated`, for all three, with `401`.

```
genuine token          200   -
alg=none               401   unauthenticated
re-signed, HS256       401   unauthenticated
tenant claim rewritten 401   unauthenticated
```

All three died at the same place, and it is earlier than most people guess. The third case had *two* things wrong with it — a rewritten tenant claim and a symmetric algorithm — and the API never got far enough to have an opinion about the first one. The claim was never read, because nothing downstream runs on a token that was refused at the door.

## Where the control lives

In step 3 of the verifier (`auth/tokens.py`): the **algorithm allowlist**, straight after the issuer the token names has chosen which rules apply. The API reads the `alg` header and checks it against a fixed set — `RS256`, `RS384`, `RS512`, `ES256`, `ES384` — *before* it looks up a key and before it verifies anything. Stripping the signature sets `alg` to `none`. Re-signing with an attacker's key sets it to `HS256`. Neither is on the list, so neither token ever reaches a key lookup, let alone a signature check.

```
raw string  →  issuer  →  algorithm  →  key + signature  →  claims  →  load subject  →  authorize  →  query
                             ↑
                       all three died here
```

**This is the control that earned its keep.** Pinning the algorithm is the cheapest line in token verification and the one most often left to the library's default — and the default, historically, has been to trust whatever the token asked for.

### A second, independent defence

Suppose the signature had been perfect — say the signing key leaked and the attacker could mint anything. `organization_id` in the token is still a string nobody reads. The API takes `sub`, and then:

```python
subject = services.memberships.load_subject(token.subject, token.authentication_level)
```

Tenant and roles come from `app.memberships`, every request (1.1's Part 2 tab). So the two defences are independent: the signature check stops people writing tokens, and loading the subject server-side stops a written token from carrying its own permissions. Each is worth having without the other, which is what makes them layers rather than one control described twice.

## What this check does not cover

Nothing was armed; the tokens were built wrong on the way out, and the lab is untouched.

- **A leaked signing key.** Someone holding Keycloak's private key can mint a valid token for **any user who exists**. The algorithm pin does nothing against that; the server-side lookup limits it to what that user may do. Bad, and a different incident — key protection and rotation.
- **A second key.** From 1.5 on, the API trusts the delegation broker's key as well, and every issuer an API trusts is a key to it. That key is narrower by design: its tokens must name an agent, may not live beyond five minutes, and are limited by their scope and by the policy's refusal to let any agent approve. It is mounted to the broker alone, and `V-32` checks that.
- **Which check failed.** The response is `401 unauthenticated` with no detail, on purpose. An error saying "signature valid but audience wrong" is a free oracle: it tells an attacker they have the right key and the wrong target. The detail exists in the API's log, where an operator can see it and a caller cannot — the same shape as the 404 in challenge 7.3.

## Take it to a review

1. **Is the accepted algorithm pinned, or read from the token?** Ask to see the line. "We use a library" is not an answer; the libraries are what made this optional.
2. **Do you check `aud`, and do you require it to be present?** Then: *what happens to a valid token minted for another service?* If nobody knows, that is the test to run while you are there.
3. **What in your authorization decision comes from a claim rather than from a lookup?** Anything on that list is something an attacker with a signing key gets for free. The one kind of claim that is safe to read is one that can only *remove* authority — a delegated token's scope is exactly that.

The third question is the one that generalises past tokens, and it is the same question as 1.3 from a different angle:

> **Identity comes from the token. Everything else comes from the server.**
