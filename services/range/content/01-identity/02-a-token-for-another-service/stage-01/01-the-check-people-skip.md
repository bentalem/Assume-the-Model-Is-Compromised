# The check people skip

A token is not a key to a building. It is a key **cut for one door**, and `aud` is the part that
says which.

Almost nobody checks it.

## The scenario the check exists for

One identity provider. Forty services. That is an entirely normal enterprise, and it is what makes
this the most valuable of the seven checks.

1. A user signs in to the expenses tool.
2. The identity provider mints them a token. Valid, signed, unexpired, naming them correctly.
3. The expenses tool receives that token — and it now **holds a working credential for that user**.
4. If the payroll API does not check `aud`, the expenses tool can present it there and be believed.

Nothing was forged. The token is exactly as issued, presented by a service that legitimately
received it.

> **Without an audience check, every service that can receive a token becomes a key to every service
> that does not check who the token was for.**

Forty services, one missing check, and the reachable set is the whole estate.

## Why it is skipped

Three reasons, and they are all boring, which is why it keeps happening.

**It looks redundant.** The signature is valid, the issuer is right, the user is real. `aud` feels
like a formality on top of three checks that already passed.

**The library makes it optional.** Most JWT libraries verify the signature by default and take the
audience as an optional parameter. Leaving it out produces working code.

**It only fails in a system nobody has built yet.** With one service there is nothing to confuse, so
it is not missed until the second service exists — and by then the verification code has been
working for a year and nobody revisits it.
