# Part 1: conversation history

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
