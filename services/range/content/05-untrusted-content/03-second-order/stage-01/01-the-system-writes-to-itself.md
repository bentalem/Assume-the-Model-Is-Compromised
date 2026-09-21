# The system writes to itself

Indirect injection needs an attacker to write the text. Second order does not. The system writes it
itself, and the next reader has no reason to be suspicious of a record its own tooling produced.

The shape is boring, which is why it survives review:

```
a customer writes something
an agent summarises the ticket into an internal note
tomorrow, another agent opens the ticket
the note is in the context, labelled internal
```

At no point did anything cross a filter, because at no point was there a filter. **Nobody filters
their own data.** The moment text is written into a table the organization owns, it stops being
treated as external and starts being treated as a record.
