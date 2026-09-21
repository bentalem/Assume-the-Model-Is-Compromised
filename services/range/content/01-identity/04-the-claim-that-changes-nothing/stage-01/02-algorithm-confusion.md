# Algorithm confusion

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
