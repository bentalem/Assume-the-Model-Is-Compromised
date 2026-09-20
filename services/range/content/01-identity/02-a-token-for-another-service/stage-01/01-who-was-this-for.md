# Who was this token for?

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

## What makes it different from the other checks

Every other check on the list catches a token that is **wrong**. Expired, unsigned, forged,
algorithm-confused — in each case something about the credential is broken and refusing it is
obviously right.

This one catches a token that is **perfect**.

That is what makes it hard to test for and easy to argue away. There is no malformed input to point
at, no exception in a log, no anomaly. The token is fine. It was simply meant for somebody else, and
knowing that requires having decided, in advance, who you are.

## Two things to ask

> **"Does your API check the audience claim? Show me the line."**

Then the better one, because it needs no code access and no trust:

> **"Take a valid token from any other service that uses this identity provider, and send it here.
> What happens?"**

That is exactly what you are about to do. The realm has a second client, `another-service`, with no
audience mapper — so its tokens are entirely legitimate and simply do not name this API.

Run the control group first.
