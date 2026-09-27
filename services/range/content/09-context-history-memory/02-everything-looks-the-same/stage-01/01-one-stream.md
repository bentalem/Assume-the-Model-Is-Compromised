# One stream

A person reading a support ticket sees structure: this is the customer, this is an internal note,
this is the system's own banner. A model sees none of it. Its context is **one sequence of text**,
and a sentence that arrived from a tool, a sentence the user typed and a sentence from a rule the
organisation approved are the same kind of thing to it.

So memory systems label. Each item in the block says where it came from:

```
- (memory; written by agent; confirmed by user; original) Prefers email over phone.
- (turn 3; tool; produced as support_agent) get_ticket TKT-1001, internal note: ...
```

That label is worth having. It tells a reviewer reading the log what the model was given and from
where. It lets the runtime, the audit trail and a human decide what to trust. It measurably helps
some models weigh what they read.

## What it does not do

It does not stop anything. A model can read "this came from a tool" and do what the tool's text says
anyway — and injected text is written to make exactly that happen. A label is more tokens in the
same stream the attacker is writing into.

This is the point the whole lab has been building to from track 5 on: **you cannot make the model
the boundary.** The label is information for the model and evidence for people. The control is what
the agent can reach, and who has to approve what it does.
