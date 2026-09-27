# Agent memory and context: the system behind track 9

This is the same architecture lesson shown in challenge 9.1's five opening Learn tabs. Read it before starting track 9. No terminal is needed for the challenges.

## 1. Start here: how the memory system works

Read these five architecture tabs before you start challenge 9.1. They explain the system you will test throughout track 9: where the data lives, how it gets there, and what the model can actually reach.

The model does not keep a PostgreSQL database inside itself. Every time it runs, an **agent runtime** decides what information to send it. Our separate memory service helps the runtime build that information. We call the result the **context block**.

We store three different things:

| Kind | What it stores | Example | What happens later |
|---|---|---|---|
| **History** | Messages and tool results from a conversation | A tool returned the status of a support ticket | Recent turns can be sent back in the next context |
| **Long-term memory** | Selected facts that may help across conversations | The user prefers short reports | Confirmed facts may be used in later chats |
| **Rules** | Instructions the agent should follow | Ask for an order number before discussing a refund | Approved rules are added to future context across the organisation |

History says **what happened**. Long-term memory says **what to remember**. Rules say **what to do**. They are separate because they need different permissions.

## The architecture

```text
Signed-in user
    |
Agent runtime (Onyx, or the lab's probe)
    |
    | user's access token
    v
Memory Service (FastAPI)
    |---- Core database: current organisation and roles
    |---- Memory PostgreSQL: history, memories, rules, logs
    |---- Local embedding model: text to numbers
    +---- Qdrant: search memories by meaning
    |
    v
Context assembly: rules + confirmed memories + allowed history
    |
    v
Agent runtime --> language model
```

The memory service is **beside the agent**, not inside its model or its main business API. It has its own database, token audience and private network.

It is written in Python with FastAPI. It uses PostgreSQL through psycopg, calls Qdrant through HTTP, and uses a separate local embedding service. It is not built on an agent framework such as LangGraph. It can serve any runtime that calls its API.

## Who is allowed to do what?

The model can ask for only four memory actions:

| Model tool | What it can request |
|---|---|
| `remember` | Save a new fact, waiting for confirmation |
| `recall` | Search confirmed facts the signed-in user may read |
| `forget` | Forget a memory that belongs to the signed-in user |
| `propose_rule` | Suggest a new instruction, waiting for approval |

The runtime, not the model, records history, builds context and asks for user confirmation. A separate authorised person decides whether a proposed rule becomes active.

The memory service does not trust a user ID, tenant ID, role or approval passed as tool input. It verifies the user's token and looks up their current organisation and roles in the core database on **every request**.

## What is real in this lab?

The memory service, both databases, the vector store and all the access checks are real. The Range's **probe plays the runtime** by saving turns and building context. Onyx still uses its own conversation history; it does not automatically write that history into our memory service.

So a context log shows exactly what our memory service **built and returned**, not proof that an external model received it.

**Next:** learn how each of the three stores works, then see how they become one context.

---

## 2. Part 1: conversation history

History is the record of a conversation. It includes the user's messages, the assistant's replies and **the results of tools**.

For example:

```text
Turn 1: user       "What happened to the export job?"
Turn 2: tool       "The job completed at 02:14."
Turn 3: assistant  "The export completed successfully."
```

When the user sends another message, the runtime may put these saved turns into the next context. That is how a model that does not remember the last API call can still follow the conversation.

## Where is it stored?

History is saved in the memory PostgreSQL database, in two tables.

| Table | One row represents | Main fields |
|---|---|---|
| `mem.sessions` | One conversation | `id`, `org_id`, `owner_sub`, `title` |
| `mem.turns` | One message or tool result | `session_id`, `seq`, `role`, `content`, `authz` |

`session_id` joins a turn to its conversation. `seq` keeps the turns in order. `role` tells us whether a turn came from the user, the tool or the assistant.

The extra field `authz` stores the user's **roles at the time the turn was written**.

```json
{
  "role": "tool",
  "content": "The restricted ticket is ready for review.",
  "authz": {
    "roles": ["support_manager"]
  }
}
```

The server gets those roles from the verified user's current membership. The model cannot supply its own value for `authz`.

## How a turn is saved

1. The runtime creates a session, then calls `POST /v1/sessions/{session_id}/turns` with the user's token.
2. The service verifies the token, looks up current roles and checks that the session belongs to that user.
3. The secret filter checks the text. If it recognises a credential, it removes the value **before saving the turn**.
4. The service writes the turn, its role snapshot and an audit event into PostgreSQL.

Row-level security in the database checks ownership again. A manager may have permission to review a colleague's transcript, but **cannot add turns to it**.

## How history returns to context

Context assembly reads at most **six recent turns**. If the runtime gives a session ID, it uses that conversation. Without a session ID, it can use recent turns from the user's other conversations.

Before replaying a `tool` or `assistant` turn, it compares the roles recorded in `authz` with the user's **current** roles. If a role was lost, that turn is left out. The context says which turn was omitted.

This is a broad **role check**, not a fresh field-by-field check against the original system. A user message is not checked this way.

## Why it matters

A transcript can become a second copy of private information. If a tool returned data using a manager's rights, that data may still be in history after the manager loses the role.

Challenge 9.1 tests a secret entering history. Challenge 9.3 tests who can read a colleague's transcript. Challenge 9.4 tests whether an old tool result is replayed after a role change.

**Read the code:** `services/memory/src/supportpilot_memory/history.py` and `database/memory/migrations/0002_history.sql`.

---

## 3. Part 2: long-term memory

History keeps the conversation. **Long-term memory keeps selected facts** that might help in a later conversation.

For example, the user tells the agent that they prefer short incident reports. The model may suggest saving this preference so it does not need to ask again tomorrow.

But a sentence in a ticket is not the same as the user's request to remember it. The model might be tricked into saving a malicious instruction. That is why our memory service separates **saving** from **confirming**.

## The life of a memory

```text
Model calls remember
       |
       v
PostgreSQL: new record, status = unconfirmed
       |
       | user confirms through a runtime-only route
       v
status = confirmed
       |
       v
Eligible for future context and recall
       |
       | owner calls forget
       v
Original, derived records and vector copies are retired
```

The model's `remember` tool only accepts text. The service decides the owner, organisation, source channel and initial status. A model-written memory is **unconfirmed by default**.

The route that confirms a memory is **not a model tool**. The runtime must call it on behalf of the user. Only confirmed records may enter the model's future context.

## Why there are two databases

`mem.records` in PostgreSQL is the **source of truth**. It holds the text, owner, organisation, source, status, confirmation, creation time and `derived_from` link for summaries.

Qdrant is a **search copy**. A local embedding model turns the text into a vector with **384 numbers**. Qdrant stores that vector **and a copy of the text** so the service can find facts with similar meanings.

The lab writes to two layouts: one Qdrant collection per organisation, and one shared collection with a tenant field. This double write is for challenge 9.6. A real deployment does not need both.

## How saving works across both stores

1. The service checks the user's identity and refuses recognised credentials as long-term memory.
2. It writes the fact, an audit event and an `outbox` job **in one PostgreSQL transaction**.
3. After commit, it asks the local embedding service to turn the text into numbers.
4. It sends the vector and payload to Qdrant, then marks the outbox job as applied.

PostgreSQL and Qdrant cannot commit one shared transaction. If Qdrant is unavailable, the PostgreSQL record still exists and the outbox job remains pending. A reconciliation check compares the stores and reports missing or stale copies.

## Two different read paths

**Automatic context:** select the user's **eight newest confirmed memories from PostgreSQL first**. Qdrant can change the order of those eight based on the new question. It does **not** select a different eight. If Qdrant is down, the same records can be shown by time.

**The `recall` tool:** search Qdrant for up to **30** candidate IDs. Then read those IDs from PostgreSQL under row-level security, returning only records the user is still allowed to see and that are confirmed. Results are paged, with up to **ten** per page.

Qdrant suggests which record may be relevant. PostgreSQL decides whether it may be returned.

## Summaries and forgetting

The runtime can make a short record from an existing memory. **In this lab, summary creation shortens text; it does not call a language model.** The new record points to its source through `derived_from`.

A full `forget` follows these links, marks the original and every derived record as forgotten, and requests deletion of their Qdrant copies. It does **not** delete old transcripts, earlier context logs or backups.

Challenge 9.5 tests who confirms a memory. Challenge 9.6 tests tenant separation in Qdrant. Challenge 9.8 tests what forgetting must remove.

**Read the code:** `memories.py`, `vectors.py` and `database/memory/migrations/0003_records.sql`.

---

## 4. Part 3: rules the agent can propose

A fact says, "The user prefers short reports." A **rule** says, "Always ask for an order number before discussing a refund."

A rule is different because it asks the agent to **behave in a certain way on future turns**. In this lab, an active rule is included in the context of users across the same organisation.

We call this **procedural memory**. Because it changes the agent's future instructions, it is also a control-plane change.

## How a rule is made

The model has the `propose_rule` tool. It accepts the proposed text only. The service gets the organisation and proposer from the verified user. It hashes the exact text and stores the proposal in `mem.rules`.

```text
Model proposes a rule
         |
         v
      proposed
      /      \
  approved  rejected
     |         |
     v         v
   active    rejected
     |
  later retired
     |
     v
   retired
```

By default, a proposal does **nothing** until it has been approved.

A user with an approver role reviews the exact text and submits its hash with the decision. The approver **cannot be the person who proposed the rule**. The service checks this, and a database trigger checks it again.

The database also limits the allowed changes of state. The rule's text and the identity of its original approver cannot be changed in place. An authorised approver may retire an active rule later, without changing who originally approved it.

## How it reaches the model

Context assembly selects **active rules in the user's organisation**. It puts them before long-term memories and chat history.

That does not give the rule power over the business API. A rule saying a refund is approved cannot bypass the separate refund approval and execution path elsewhere in this lab.

## What challenge 9.7 breaks

When `rules.self_activate` is enabled, a model proposal becomes `active` immediately. If the model proposed that text after reading a malicious note, that note may become an instruction for future conversations across the organisation.

Turning self-activation off only protects **new** proposals. Rules that were activated while it was on remain active. The Range's restore also retires rules that became active without approval.

**Read the code:** `rules.py`, `database/memory/migrations/0004_rules.sql` and `0008_rule_retirement.sql`.

---

## 5. Part 4: building the context

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

## Which challenge tests each part?

| Challenge | The question you will answer |
|---|---|
| 9.1 | What happens when a secret is saved in history and replayed? |
| 9.2 | Do source labels stop a model from following untrusted text? |
| 9.3 | Who can read a colleague's saved conversation? |
| 9.4 | What happens to an old tool result after the user loses a role? |
| 9.5 | Can the model make its own unconfirmed memory active? |
| 9.6 | What protects another organisation's data in a vector store? |
| 9.7 | Can the model make its own proposed rule active? |
| 9.8 | How many copies survive when a user asks to forget a memory? |

Read the [memory stack setup](../../LAB.md#a6--the-memory-stack-track-9) to start the services. The Range's probe plays the agent runtime for track 9; the memory system's access checks and stores are real.
