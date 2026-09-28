# Start here: where untrusted text meets the agent

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
