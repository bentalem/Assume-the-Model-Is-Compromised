# The fourth architecture

Challenge 1.1 laid out four answers to one question — what goes in the `Authorization` header when an agent calls a tool — and ran two of them. Passthrough (C) beat the service account (A), because the agent can never reach more than the signed-in user already could.

That makes C the best of the classic three. It is not good, and this challenge is the fourth answer.

## The problem with passthrough

An agent is a **deputy**: it acts for someone else. Under passthrough the deputy holds *all* of the principal's authority, whatever it was asked to do. Ask it where an order is, and it is carrying a token that can also read every customer, add notes to tickets and propose refunds.

Most of the time that does not matter, because the agent only does what it was asked. The day it matters is the day the agent reads a ticket an attacker wrote and decides its next call from that text. A successful injection then gets everything the user can do. That is **ambient authority**: present regardless of the task, and waiting to be used.

> Least privilege has to be **per task**, not per user.

## Four architectures

| | In the token | How much power the agent has | Can you see the agent did it? |
|---|---|---|---|
| **A** Service account | the agent only | the union of every user's permissions | yes, but not for whom |
| **B** Service account plus claimed user | the agent; the user as a forgeable parameter | the same as A | only apparently |
| **C** Passthrough | the user only | everything the user can do | **no** — agent and user are indistinguishable |
| **D** Down-scoped delegation | both, signed | the intersection | yes — who asked, and who acted |

## Two ideas that are easy to confuse

D is two separate improvements, and a system can have one without the other.

- **Delegation** gives the agent its own token that says *user X delegated to agent Y*. It fixes **attribution**: the trail can tell the person from the agent acting for them. On its own the token can still be as broad as the user.
- **Down-scoping** makes that token deliberately narrow: only what this task needs, for only as long as the task takes. It fixes **blast radius**.

Architecture D is both. A delegated token that is not narrowed is passthrough with better logging. A narrowed token that does not name the agent limits the damage and still leaves the trail unable to say who did it.

**Next:** what is inside a delegated token, and how one is made.
