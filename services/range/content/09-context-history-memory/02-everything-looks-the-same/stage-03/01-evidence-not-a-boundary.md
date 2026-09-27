# What the source labels really changed

## What your result proves

Removing source labels changed the **text shown to the model**, but not the underlying items. The same rule, memory and history content was selected. In the item-by-item observation, the service still recorded which item came from a tool.

This tells you two different things. The rendered text is what the runtime could send to the model. The structured context log is the record that an investigator can use later. You do not need to erase the audit record just to test an unlabelled context.

## Where the labels are added

In `context.py`, the service selects the allowed items first. It then checks `context.provenance` when it renders the block. With the setting enabled, the output includes a label for each item and a warning that retrieved text is not an instruction unless it is an approved rule.

The service writes the rendered block and the item list to `mem.context_log` together with an audit event. Turning labels off does not change how the item list is stored.

## Why a label is not the boundary

A tool result may contain an instruction that looks important. Adding a label such as `tool` gives the model useful information, but the model may still act on that text. Labelling cannot force a particular decision.

Other controls make different decisions **outside the model**: unconfirmed memories are excluded, old history is checked against current roles, proposed rules need approval, and business tools enforce permissions before carrying out actions.

Keep the labels for review and for clearer context. Do not treat them as proof that untrusted instructions cannot affect the model.

## Take it to a review

- Can you tell where each context item came from after an incident?
- Is the source still saved when it is missing from the text sent to the model?
- Which controls would refuse an unsafe action even if the model followed a tool result?
- Can a retrieved instruction become an active rule without separate approval?
