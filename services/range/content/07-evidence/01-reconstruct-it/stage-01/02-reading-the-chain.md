# How to read the chain

Four rows, oldest first. Work through them in order and write down the six answers as you go.

## What each step is

| Step | Who | What it means |
|---|---|---|
| `refund.propose` | the agent's user | a request was created. **No money moved** |
| `refund.approve.view` | the approver | somebody opened the request and looked at it |
| `refund.approve` | the approver | the exact payload was approved |
| `refund.execute` | the worker | the effect happened, once |

`refund.approve.view` is worth a second of attention. It records that the approver *looked*, which
is the difference between an approval and a click. If your approvals have no view event, you cannot
tell those apart afterwards, and "the approver did not read it" is the most common thing that turns
out to be true.

## The integrity question

Proposal and execution are separated by seconds and by a queue. In between, the payload is sitting
in a table.

So: **how do you know the thing that was approved is the thing that was executed?**

Not from the decisions — every one of them says the step succeeded. The answer is a value that
appears on three of the four rows and is either identical across them or is not.

If it is identical, the approval is bound to that exact payload and nothing between approve and
execute changed the amount. If it differs, you have found the incident, and challenge 6.1 is where
you go to watch it happen deliberately.

> An approval that is not bound to a payload hash approves **the idea of a refund**, not a refund.

## Two notes on reading identifiers

**The trail gives you ids, not names.** `actor_id` is a uuid. Resolving it to a person is the
directory's job, not the log's — a log that copies display names is a log that is wrong the day
someone gets married. Resolving one to a person is a lookup this trail does not do for you — which
is itself worth noticing, because it is the step an investigator always has to take and rarely has.

**One actor is not a person at all.** The executing row's actor is a workload, and its `actor_type`
says so. That distinction is load-bearing in an agent system: some of your actors are software, and
an investigation that assumes every actor is a human being will ask the wrong questions about intent.

---

Now go and read it. Answer the six questions, then answer the integrity question, and the flag is
the second half of that.
