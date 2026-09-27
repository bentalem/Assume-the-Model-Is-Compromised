# Evidence, not a boundary

What the service does when it assembles alice's block:

1. **Reads `context.provenance`** once, in the transaction that selects the items.
2. **Selects** active rules, alice's confirmed memories, and the tail of her history — row-level security making each of them hers or her organisation's.
3. **Renders** each item. With provenance on, every line is prefixed with where it came from, and the block opens by saying that retrieved text is information, not instruction, unless it is an approved rule.
4. **Logs** the block and one record per item — kind, source, whether it was included — to `mem.context_log`, with the audit event, in one transaction.

Step 4 happens whether or not step 3 labelled anything. That is why the item view in Stage 02 could
tell you which line came from a tool even when the rendered block could not: **the evidence is kept
for people, independent of what the model was shown.**

## Where the label sits among the controls

| Control | Where it acts | If the model ignores it |
|---|---|---|
| Provenance label | in the text the model reads | nothing happens |
| Confirmation of memories (9.5) | before the text exists | the model never had the choice |
| Re-authorisation of history (9.4) | before the text is included | the model never had the choice |
| Approval of rules (9.7) | before the rule is active | the model never had the choice |
| Tool authority and approvals (tracks 4, 6) | after the model decides | the action is refused anyway |

Four of the five do not depend on the model at all. Keep the label — and never write a design
document in which it is the reason something is safe.
