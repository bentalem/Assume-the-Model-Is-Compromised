# Untrusted content: the system behind track 5

This is the same architecture lesson shown in challenge 5.1's two opening Learn tabs. Read it before starting track 5. No terminal is needed for the challenges.

## 1. Start here: where untrusted text meets the agent

Read these two architecture tabs before you start challenge 5.1. They explain the part of the system track 5 is about: where text written by someone else reaches the model, what that text can and cannot change, and where the model's own output goes next.

A language model has one input channel. Instructions from the organisation, the user's question and a customer's complaint all arrive as the same kind of thing — text in the context — with no separator between "what to do" and "what to read". So this track does not ask how to keep instructions out. It asks: **assume the text got in and the model did exactly what it said — what could it reach?**

## The architecture

```text
A customer writes on a ticket
    |
    v
app.ticket_messages  (author_kind: customer · agent · system;  visibility: public · internal · restricted)
    |
    |  get_ticket, called in alice's session with alice's token
    |  row policy drops 'restricted' messages unless the caller is a manager or an auditor
    v
The response: for each message, author_kind, body (at most 4000 characters), created_at
    |
    v
The model's context  ——  the same context as alice's own question
    |
    |  the model may now call any of the seven tools, with any arguments their schemas allow
    v
The API: token -> person -> record -> policy -> database   (tracks 1 to 4)
    |
    |  and some of its output travels on:
    |    add_internal_note  -> a row in app.internal_notes
    |    propose_refund     -> a pending request -> the approval portal renders it to a human
```

## What text can change, and what it cannot

Every input to an authorization decision is assembled from the verified token and the database **before** any ticket text is read. So a sentence in a ticket can influence exactly two things:

| Text can influence | Text cannot reach |
|---|---|
| **which** of the seven tools the model calls | who the caller is — it comes from the token |
| **which arguments** it passes, within each schema | the caller's tenant or roles — they come from `app.memberships` |
| | whether an approval exists — it is a row bound to a payload hash |
| | a secret — none is ever placed in the model's context |
| | a tool that is not registered — it does not exist to be called |

The ceiling of any injection is therefore the ceiling of the session it lands in: the caller's own authority, spent through the seven tools.

## What is real in this lab?

The ticket, its eleven messages and the read path are real. TKT-1001 carries the lab's **injection corpus**: one genuine complaint, nine instruction-shaped messages, and one restricted note.

What the Range does **not** run is a language model. Nothing here watches a model obey or refuse, because two identical runs produce different tool calls and "it refused" proves nothing you could retest. Every challenge in this track measures the boundary around the model instead — what the text could have reached if the model had done everything it asked.

**Next:** the three kinds of untrusted text, and the question that tells them apart.

## 2. Part 1: three kinds, and one question

Every piece of untrusted text raises the same two-part question:

> **Who wrote this, and whose permissions does it run under?**

The answer sorts it into one of three kinds, and the kind decides whether you have found a vulnerability.

| Kind | Who wrote the text | Whose permissions it runs under | A boundary crossed? | In this track |
|---|---|---|---|---|
| **Direct** | the caller | the caller | none — they already had that authority | 5.1 |
| **Indirect** | somebody else — a customer | the caller — a support agent | **yes**: the author borrows authority they do not hold | 5.2 |
| **Second order** | the system's own earlier output | whoever reads it next | yes, later, and under a trusted label | 5.3 |

And a fourth question, about the other direction: **where does the model's output go?** Into a note someone reads tomorrow, into a field a human approves money from. Output is somebody else's input. That is 5.4.

## Where each kind can travel in this lab

| Path | Writes to | Read back by | Closed loop? |
|---|---|---|---|
| A customer writes on a ticket | `app.ticket_messages` | `get_ticket` | yes — that is indirect injection |
| The agent adds an internal note | `app.internal_notes` | **no registered tool** | no — the return path does not exist here |
| The agent proposes a refund | `app.action_requests` | the approval portal, rendered to a human | yes, but only fixed, validated fields |
| The agent remembers something (track 9) | the memory service | the next context block | yes — track 9 is about this loop |

## What is filtered, and what is not

There is **no content filter** in this lab: no injection detector, no classifier, no scrubber. Instruction-shaped text arrives intact and is read like anything else.

One thing is filtered, and it is not a filter for instructions. The row policy on `app.ticket_messages` drops messages marked `restricted` for anyone who is not a manager or an auditor. Alice, a support agent, sees ten of TKT-1001's eleven messages — and the reason is her role, not the content.

That is the design: the protection is not in recognising dangerous text. It is in what a session can reach once the text has done its worst.

## Which challenge tests each part?

| Challenge | The question you will answer |
|---|---|
| 5.1 | When the caller writes the injection, what could it gain? |
| 5.2 | Nine instructions from a customer: why did none of them achieve anything? |
| 5.3 | When the system writes to itself, what changes about the text on the way through? |
| 5.4 | Where the model's output is rendered for a human, what could it have put there? |

**Read the code:** `database/seeds/0002_tickets_and_injection_corpus.sql`, `services/api/src/supportpilot_api/tools/tickets.py`, `database/migrations/0006_tickets.sql`.

**Now start challenge 5.1.**
