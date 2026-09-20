# What a verifier has to check

"Is the signature valid" is one of seven questions, and it is the one everybody implements.

| Check | What it stops |
|---|---|
| Signature | a forged token |
| **Algorithm allowlist** | **`alg: none`, and HS256 confusion** |
| Issuer | a token from an identity provider the attacker controls |
| **Audience** | **a genuine token minted for a different service, replayed here** |
| `exp` / `nbf` | replay of an expired token |
| `typ` / `azp` | a refresh token or an ID token used as an access token |
| `kid` | key rotation |

The two in bold are the ones most often missing, for opposite reasons. The algorithm check is
missing because the library made it optional. The audience check is missing because nobody thought
to ask.

## `alg: none`

The JWT specification includes an algorithm called `none`, meaning "unsigned". It exists for tokens
that are protected some other way.

A verifier that reads `alg` from the header and does what it says will read `none`, skip the
signature check, and accept a token the attacker wrote entirely.

The fix is one line, and it is not "reject `none`" — it is **pin the algorithm**. Decide in advance
which algorithms you accept and refuse everything else, so a future header value nobody has thought
of is refused rather than dispatched on.

## Algorithm confusion

Subtler, and the reason the fix is a pin rather than a blocklist.

Your identity provider signs with RS256: a private key signs, a public key verifies. The public key
is public — it is published at a URL, and it is supposed to be.

An attacker takes a real token, changes the header to `HS256`, and signs it using **your public key
as the HMAC secret**. A verifier that trusts the header's `alg` now runs HMAC verification with a
key both sides know, and it matches.

Nothing was broken. The verifier did exactly what the token asked it to do, and the token asked for
the wrong thing.

> **Never let the token choose how it is verified.** The algorithm is a property of your trust
> configuration, not of the credential being presented.

## Audience, and why it is skipped

Several services trust one identity provider. A user gets a legitimate token for service A.

If service B does not check `aud`, that same token works on B. Nobody forged anything — the token is
genuine, signed, unexpired and correctly issued, and it was never meant for B.

The consequence is worth stating plainly: **every service that can issue a token becomes a key to
every other service that does not check who the token was for.** In an organisation with one
identity provider and forty services, that is a very large graph.

## And the claim that is not a fact

The last case you will run rewrites `organization_id` inside the token before re-signing it.

Think about what that would have achieved with a *perfect* signature. In this lab, nothing: the API
takes the `sub` claim and nothing else, then loads the tenant and the roles from `app.memberships`.
A rewritten tenant claim is a string nobody reads.

That is the difference between a system where a token says **who** and one where it says **what**.

> A claim is something the token asserts. A fact is something the server looked up. Only one of them
> survives an attacker who can write tokens — and the whole point of checking signatures is that you
> are betting nobody can.

Both defences are worth having, and this challenge is a chance to notice that they are independent.
