# Confirmation must be outside the model

The `remember` tool accepts only a fact to save. The service fixes the source to `agent` and normally saves it as `unconfirmed`. PostgreSQL's insert policy enforces that choice too.

Context assembly selects only confirmed memories. A separate runtime route lets the user confirm a pending record. The model cannot call that route through its memory action document.

Turning on `write.auto_confirm` lets the same tool call create a confirmed record immediately. That means untrusted ticket text can become persistent context without a person's decision.

Turning the setting back off only changes new writes. The Range's restore also returns auto-confirmed records to the pending state so they stop entering context.

## Take it to a review

- Can the model mark a memory confirmed in its own tool call?
- Who can see and approve pending memories?
- How do you find memories that were auto-confirmed while the setting was unsafe?
- Does deleting a poisoned memory also remove its summaries and vector copies?
