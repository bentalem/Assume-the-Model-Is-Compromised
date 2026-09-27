# How many copies does one memory make?

alice tells the agent: *the customer on TKT-1003 asked us to call this number until the case closes.*
She confirms it should be remembered. Here is where it now lives:

| Copy | Why it exists |
|---|---|
| the record in memory-db | the source of truth, with its provenance |
| a point in `memories__cedar` | per-tenant recall |
| a point in `memories__shared` | the shared layout (this lab writes both) |
| a summary record | memory layers summarise to keep context small |
| the summary's two points | the summary is recalled like any memory |

Six copies of one fact, and that is before backups, logs or the context blocks it has already
appeared in. Real memory layers add more: extracted entities, graph edges, cached embeddings.

Then the case closes and alice says: **forget it.**

## What "forget" has to mean

A forget that removes the record and leaves the summary has not forgotten anything that matters.
The summary is recalled, selected into context and read by the model exactly like the original — it
*is* the original, shorter. A forget that removes both records and leaves the vectors has left the
content in a store that can be queried directly, as 9.6 showed.

This service's `forget` walks the derivation tree — everything whose `derived_from` leads back to
the record — and removes every record in it and every point for each, in both layouts.
