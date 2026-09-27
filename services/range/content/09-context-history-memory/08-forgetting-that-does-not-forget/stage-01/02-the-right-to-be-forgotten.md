# No single incident — a question every deletion request raises

There is no famous breach for this. It is found when somebody asks for their data to be deleted and
an engineer has to answer honestly where it is. The
[right to erasure](https://gdpr-info.eu/art-17-gdpr/) turned that from good practice into an
obligation for personal data in the EU — and derived data is personal data too.

The engineering question is the same whatever the law:

> **For one fact the user asked us to forget, list every place a copy of it exists, and show that
> each one is gone.**

A memory layer makes that list long by design, and it grows silently — a new summarisation feature,
a second index, a cache — each one a new place a delete has to reach.

## What you are about to run

The observation plays alice and the runtime. It stores a fresh memory each time (forgetting is one
way, so a seeded one would work once), confirms it, has the runtime summarise it, and then forgets
it. Then it looks in memory-db for the record and everything derived from it, and asks both vector
collections — with the Range's read-only tokens — whether a point for each is still there.
