# Part 4: building the context

History, long-term memory and rules are stored separately. The model sees none of those database tables directly.

The runtime asks `POST /v1/context` for a context block. It sends the current question, optionally a session ID, and the signed-in user's token.

The code that builds the block is in `services/memory/src/supportpilot_memory/context.py`.

## The exact order

1. **Identify the caller.** Verify the token for the memory service, then load current organisation and roles from the core database.
2. **Select rules.** Read all active rules for that organisation.
3. **Select memories.** Read up to eight newest confirmed memories owned by the user. Ask Qdrant to order those eight by meaning, if it is available.
4. **Select history.** Read up to six recent turns belonging to the user. Use the requested session if one was given.
5. **Check old roles.** Drop tool and assistant turns produced under roles the user no longer holds.
6. **Build the text.** Put rules first, then memories, then history. Label each item with where it came from.
7. **Save evidence.** Write the block and a structured list of included and omitted items to `mem.context_log`, with an audit event.
8. **Return the block.** The runtime decides how to send it in the model's next request.

Example of a possible block:

```text
[rules]
- (rule; approved by another person)
  Ask for the order number before discussing a refund.

[memories]
- (memory; written by agent; confirmed by user; original)
  The user prefers short incident reports.

[history]
- (turn 1; user; produced as support_agent)
  Summarise the open ticket.
- (turn 2; tool; produced as support_agent)
  The last update says the job completed.
```

These labels help an investigator understand where each line came from. **They are not a security boundary.** The model can still follow an instruction hidden in a labelled tool result. The real controls are which items get selected, who can read them, which tools are available and which actions need approval.

## Two details that are easy to miss

**The two memory searches are different.** Automatic context selects recent confirmed memories first, then sorts them. The model's `recall` tool does a broader semantic search and checks each candidate again in PostgreSQL.

**The context log is another sensitive copy.** It stores the text the memory service returned, even if a memory is deleted later. The current lab's probe plays the runtime, so this log proves what the service built, not exactly what an external model saw.

## Follow one request

```text
User request
  -> runtime asks for context
  -> service checks identity and current roles
  -> PostgreSQL returns allowed rules, memories, history
  -> Qdrant may reorder selected memories
  -> service checks history permissions and labels sources
  -> context block + audit saved
  -> block returned to runtime
  -> runtime sends the next request to the model
```

The model may propose a memory or a rule. It cannot confirm a memory, approve its own rule, choose another user's identity or change the database policies.

**Now start challenge 9.1.** You will follow one tool result from the moment it is stored until it appears in the next context.
