# Four architectures

When an agent calls a tool, something goes in the `Authorization` header. There are four
possibilities, and which one you choose constrains everything else you will ever do about security in
that system.

| | What is in the header | If the model is steered | Can you tell afterwards who acted? |
|---|---|---|---|
| **A** Service account | the agent's own credential | the union of every user's permissions | the agent, but not for whom |
| **B** Service account plus claimed user | the agent's credential, user id as a parameter | the same as A, and it *looks* like per-user access control | only apparently |
| **C** Passthrough | the signed-in user's own token | everything that one user can do, whatever the task | **no** — the agent and the user are indistinguishable |
| **D** Down-scoped delegation | a token naming the user **and** the agent, narrowed to the task | only what the user, the agent and the task all allow | yes — who asked, and who acted |

A, B and C are the classic set, and most agents in production today use one of them. D is what an
organisation reaches for once it sees what C costs: C bounds the damage to one user, but it still
hands the agent **all** of that user's authority, for as long as the token lives.

This challenge runs **A against C**: the same two questions, first with the user's own token and
then with the agent's own account. B is explained in the next tab and deliberately not armable —
building it would mean adding the forgeable parameter the lab exists to forbid.

**D has its own four challenges, 1.5 to 1.8.** They add a delegation broker beside the API and
show the four ordinary ways D is lost again: a passthrough fallback, a scope nobody checks, an agent
that sets its own scope, and a chain that widens.
