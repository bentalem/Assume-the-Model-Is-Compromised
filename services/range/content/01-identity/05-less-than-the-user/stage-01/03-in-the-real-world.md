# In the real world

The concept has several names — scoped or down-scoped delegation, attenuation, constrained delegation — and no single standard label. The shape is the same everywhere: the effective permission is an **intersection**, and something other than the agent decides it.

- **GitHub.** An app acting for a user can reach only what the user can reach *and* what the app was granted, and the audit log records the user with the programmatic access type. Fine-grained tokens are limited to chosen repositories and permissions. The Copilot coding agent pushes only to its own branch, cannot approve or merge its own pull request — and the person who asked it cannot approve that pull request either.
- **AWS.** Temporary credentials with a session policy: the effective permission is the intersection of the role and the session policy. The same formula.
- **Google Cloud.** Downscoped credentials limited to one bucket or a set of objects.
- **Microsoft Entra Agent ID.** Each agent has its own identity and acts for users through an on-behalf-of flow, with delegated permissions and consent.
- **Brokers.** Credential brokers mint scoped subsets of a user's credentials for agents — an administrator's agent that can only read — and short-lived, narrowly scoped tokens per interaction.
- **Standards.** OAuth 2.0 Token Exchange, RFC 8693 (`act`, `may_act`); Rich Authorization Requests, RFC 9396 (a request naming the exact resource and actions); an IETF draft on on-behalf-of authorisation specifically for AI agents.

## The bridge from offensive security: Kerberos

If you have attacked Active Directory, you have seen all four architectures already.

| Kerberos | The same idea here |
|---|---|
| **Unconstrained delegation**: the service holds the user's ticket-granting ticket and can act as them anywhere | passthrough (C) |
| **Constrained delegation**: act for the user, but only towards listed services | down-scoped delegation (D) |
| **Resource-based constrained delegation**: the resource decides who may delegate to it | what happens when the wrong party decides the constraint — challenge 1.7 |

A host with unconstrained delegation is a prize precisely because of ambient authority: every ticket that touches it can be replayed anywhere. An agent under passthrough is the same prize.

## Why this lab has its own broker

The lab's identity provider is Keycloak 26.0.7. Keycloak supports standard token exchange from 26.2, including narrowing the audience; delegation with `act` was not supported even there when this lab was written (it is tracked as preview work). Upgrading the part of the lab that works best, for a feature it would still only half have, was the wrong trade.

So the broker implements RFC 8693 itself, which is also how several organisations do it today. If Keycloak gains supported delegation later, the broker can be replaced by it without changing this challenge's lesson.

**Next:** what you are about to run.
