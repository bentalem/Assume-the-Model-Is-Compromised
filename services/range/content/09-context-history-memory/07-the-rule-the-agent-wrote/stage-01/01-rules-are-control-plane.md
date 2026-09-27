# Rules are control-plane state

Memory systems have three kinds of memory, and the third is the one people forget is different:

| Kind | Example | What the model does with it |
|---|---|---|
| Episodic — history | "yesterday alice asked about ORD-2001" | reads it |
| Semantic — facts | "alice prefers email" | reads it |
| **Procedural — rules** | "always confirm the order number before discussing a refund" | **obeys it, every turn** |

A rule is an instruction with standing. It applies to every conversation, for everyone it covers,
until somebody removes it. Changing one is a change to how the agent behaves — which is what track 8
calls the control plane.

So the question is the one track 6 asked about refunds: **who proposes, who approves, and can they be
the same party?** Here the proposer is often the model itself. Assistants that "learn your
preferences" are writing rules for themselves from what they read.

## What this service does

`propose_rule` is one of the four tools the model has. It creates a proposal. A proposal does
nothing until someone else approves the exact text — by its hash — through a route the model does not
have. The store enforces that the approver is not the proposer, in a trigger, whoever is calling.
