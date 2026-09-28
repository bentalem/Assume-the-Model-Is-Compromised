# The wrong party decides

Every real delegation system has a place where the ceiling is written down, and the attacks against those systems are usually about who gets to write there.

## Kerberos: resource-based constrained delegation

Classic constrained delegation puts the constraint on the **delegating** service: a domain administrator lists which services it may act for users towards. Resource-based constrained delegation (RBCD) moved that decision to the **resource**: the target service lists who may delegate to it, in an attribute on its own account.

That is a reasonable design, and it is a well-known attack path. Anyone who can write that attribute on a target — through a misconfigured permission, or a relayed authentication — can add a machine they control to the list and then act, as any user, towards the target. The protocol is working exactly as designed. The wrong party decided the constraint.

It is the same shape as this challenge: the limit exists, and the party that was supposed to set it is not the one setting it.

## The same idea elsewhere

- **AWS session policies.** A role assumed with a session policy gets the intersection of the two. The session policy is supplied by whoever calls `AssumeRole`. If that caller is the agent, the agent is setting its own third term — and passing the role's full permissions as the session policy is always allowed.
- **Consent screens.** An OAuth client asks for scopes and the user approves. When the "client" is an agent choosing its own requested scopes per task, and approval is automatic, nobody is approving anything.
- **Credential brokers.** The products that mint scoped credentials for agents all hold the ceiling themselves, as configuration an administrator sets. None of them lets the agent's request be the ceiling.

## What this lab refuses however it is configured

One scope is outside every switch: `refunds:approve`. It is listed as never delegable in the scope table. The broker will not mint it, will not start if a profile's ceiling includes it, and the policy refuses a delegated approval even if a token carrying it arrived anyway. Track 6's separation of duty, applied to agents — the same line GitHub draws when its coding agent cannot approve its own pull request.

**Next:** what you are about to run.
