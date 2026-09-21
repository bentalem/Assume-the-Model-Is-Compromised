# What makes it different

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
