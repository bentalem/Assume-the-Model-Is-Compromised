# The field that does not survive

The answer to "what changed on the way through" is in two files, three lines apart in effect.

The query loads five columns for every message:

```
m.id, m.author_kind, m.body, m.visibility, m.created_at
```

The response model declares three:

```
author_kind, body, created_at
```

`visibility` is selected, used by nothing, and dropped on the way out. The model that reads this
ticket is told **who** wrote each message and never told **where it was meant to be seen.** An
internal escalation note and a public customer reply arrive looking identical apart from one word in
`author_kind`.

That is not a bug, and saying it is one would be the wrong finding. The response is bounded on
purpose — `extra="forbid"`, a named field list, a capped body — and adding a field to a model
context is a decision, not a default. The observation is narrower and more useful:

> The only signal a later reader gets about provenance is `author_kind`, and `author_kind` says
> `agent` for text a customer originally supplied.

## Trace it, column by column

| Stage | Who wrote it | What the record says | Authority it carries |
|---|---|---|---|
| Customer types it into a ticket | a customer | `author_kind = customer` | none |
| An agent summarises it into a note | an assistant, on alice's token | `author_id` = alice, server-derived | alice's, at write time |
| A later session reads it back | nobody new | `author_kind = agent` | none — it is a string again |

The middle row is where authorship is manufactured, and it is manufactured correctly: `notes.py`
takes `author_id` from the verified subject, the insert policy in migration `0007` refuses any other
value, and the request schema has no author field at all. The system is not wrong about who wrote
the note. It is wrong about nothing.

The text still changed status. It arrived as customer data and left as a staff record, and every
control in the path did its job.

## What did not change

Nothing about the authority behind it.

That sentence is the flag, and it is also the reason this is survivable. The note can say the refund
policy allows automatic approval under 1000 USD as often as it likes. There is no code path in which
a sentence in a ticket message changes:

- what `propose_refund` freezes into a payload;
- whether an approval row exists;
- whose identity is on that approval;
- whether the worker's recomputed hash matches.

The promotion is real, and it buys the attacker exactly nothing — *in this system*. In a system
where the summary is read by something that acts on it without a second check, the same promotion is
the whole attack.

## The two layers, and which one you would have to ask about

The policy comment on `ticket.read` is worth reading in the source panel because it states the split
honestly:

```
Restricted messages are filtered by the database row policy, not here. This
decides access to the ticket; the database decides which messages within it
are visible.
```

So there are two places to ask about provenance, and they answer different questions. The policy
never sees a message. The row policy sees every message and has an opinion about exactly one
visibility value. If you want a rule that treats `internal` as untrusted-until-proven, neither of
those is currently the place it lives — and picking which one it should live in is a design
conversation, not a patch.

## Take it to a review

1. Ask what the agent writes, and where it writes it. Summaries, notes, tags, ticket titles,
   resolution text, CRM fields. Every one of them is a future input to something.
2. For each of those, ask which read path returns it and to whom. If any write lands in a store that
   a later session reads, the loop is closed and you have a second-order channel.
3. Ask whether the later reader can tell where the text came from. Get the actual response schema,
   not the table schema. A provenance column that the API loads and does not return is worth naming
   precisely, because the fix is small and the gap is invisible from the database side.
4. Ask what happens to the earliest author's identity. If the trail records only the agent that
   wrote the summary, the person who supplied the words is not in the evidence, and an incident
   reconstructed a month later will stop at the wrong name.
5. Do not recommend filtering the summary. Recommend deciding, for each store the agent writes into,
   whether its contents are treated as data or as instruction by whatever reads them next — and then
   check the answer against the code rather than the intent.
6. Say plainly whether the loop is closed in the system you are reviewing. "It would be second-order
   injection if `get_ticket` returned internal notes, and it does not" is a finding a team can act
   on. "Second-order injection is possible" is not.
