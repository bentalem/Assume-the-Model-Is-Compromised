# A claim is not a fact

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
