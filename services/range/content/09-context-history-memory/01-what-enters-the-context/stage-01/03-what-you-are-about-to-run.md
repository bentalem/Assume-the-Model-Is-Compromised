# What you are about to run

The observation plays **the agent runtime** — the component that writes history and builds context.
No model is involved; none is needed to see what a model would be given.

1. It opens a new session for alice.
2. It stores a tool turn: a deploy log that includes an AWS-style access key. The key is AWS's own documented example value, which the lab's secret scanner and a human both read as test data.
3. It asks the memory service to assemble alice's context for that session.
4. It shows you the block exactly as the service logged it, item by item.

Run it first with nothing armed and look at the tool turn. Then arm the control and run it again.

The `secret_shaped` column is filled only when something credential-shaped is in an item that was
**included** in the block — that is, something the model would have read.
