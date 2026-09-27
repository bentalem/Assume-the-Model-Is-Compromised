# Start here: how the memory system works

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
