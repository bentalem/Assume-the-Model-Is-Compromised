# Source labels help; they do not enforce trust

Context assembly selects active rules, confirmed memories and the user's recent history. It can label every line with its source.

With labels turned off, the same content still reaches the context. The structured record in `mem.context_log` still stores each item's source and whether it was included.

A label is useful evidence. It may help a model treat retrieved text as data, but it does **not** force the model to ignore a malicious instruction.

The enforceable controls act outside the model: decide which memory enters context, check old permissions again, require approval for rules and restrict tool authority.

## Take it to a review

- Where is source information stored when the rendered label is removed?
- Could a tool result become an active rule without human approval?
- What would stop an unsafe action if the model followed the injected text?
