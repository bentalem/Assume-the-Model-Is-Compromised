# Part 1: three kinds, and one question

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
