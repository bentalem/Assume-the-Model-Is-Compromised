# Dead at the first check

`unauthenticated`, for all three, with `401`.

```
genuine token         200   -
alg=none              401   unauthenticated
re-signed, HS256      401   unauthenticated
tenant claim rewritten 401  unauthenticated
```

## Why all three are identical

Because all three died at the same place: **signature verification**, the first thing that happens
after the string is pulled off the header.

The third case had *two* things wrong with it — a rewritten tenant claim and an invalid signature —
and the API never got far enough to have an opinion about the first one. The claim was never read,
because nothing after verification runs on a token that did not verify.

That is the correct order, and it is worth noticing that it is an order at all:

```
raw string  →  verify  →  identify  →  load subject  →  authorize  →  query
                 ↑
            all three died here
```

## The claim would have changed nothing anyway

Suppose the signature had been perfect — say the signing key leaked and the attacker could mint
anything.

`organization_id` in the token is still a string nobody reads. The API takes `sub`, and then:

```python
subject = services.memberships.load_subject(token.subject, token.authentication_level)
```

Tenant and roles come from `app.memberships`, every request. An attacker with the signing key could
impersonate **a user who exists** — bad, and a different incident — but could not invent a tenant
membership, because that is a row in a table rather than a claim in a credential.

> **Two independent defences.** The signature check stops people writing tokens. Loading the subject
> server-side stops a written token from carrying its own permissions. Each is worth having without
> the other, which is what makes them layers rather than one control described twice.

Most systems have the first. The second is the one worth asking about.

## Why the response says so little

`401 unauthenticated`, with no detail about *which* check failed.

That is deliberate. An error saying "signature valid but audience wrong" is a free oracle: it tells
an attacker they have the right key and the wrong target, which is exactly the information that
turns a dead end into a next step.

The detail exists — in the API's logs, with the reason — where an operator can see it and a caller
cannot. Same shape as the 404 in challenge 7.3: **opaque outward, specific inward.**

## What to ask a client

1. **Is the accepted algorithm pinned, or read from the token?** Ask to see the line. "We use a
   library" is not an answer; the libraries are what made this optional.
2. **Do you check `aud`?** Then: *what happens to a valid token minted for another service?* If
   nobody knows, that is the test to run while you are there.
3. **What in your authorization decision comes from a claim rather than from a lookup?** Anything on
   that list is something an attacker with a signing key gets for free.

The third question is the one that generalises past tokens, and it is the same question as 1.3 from
a different angle:

> **Identity comes from the token. Everything else comes from the server.**
