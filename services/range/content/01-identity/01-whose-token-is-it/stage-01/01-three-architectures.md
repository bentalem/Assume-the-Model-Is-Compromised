# Three architectures

When an agent calls a tool, something goes in the `Authorization` header. There are three
possibilities, and which one you chose constrains everything else you will ever do about security in
that system.

| | What is in the header | If the model is steered |
|---|---|---|
| **A** Service account | the agent's own credential | the union of every user's permissions |
| **B** Service account plus claimed user | the agent's credential, user id as a parameter | the same, and it *looks* like per-user access control |
| **C** Passthrough | the signed-in user's own token | what that one user already had |

There is a fourth architecture, down-scoped delegation, in which the token names both the user and the agent and carries only what the task needs. It is challenge 1.5.
