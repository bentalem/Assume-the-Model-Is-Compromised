# Check at the moment of use

The decision chain for one replayed turn:

1. **At write**, the runtime appends bob's tool turn. The service captures `authz` — `{"roles": ["support_manager"], "at": ...}` — from bob's verified principal. The caller cannot supply it.
2. **At replay**, the service resolves bob's principal again from the core database. His roles are what they are *now*.
3. **For each tool or assistant turn**, it compares the roles the turn was produced under with the roles bob holds now. Any role lost means the turn is omitted, and the block says which role.
4. **The log records both** — `produced_under`, `roles_now`, `included`, and whether an included item `outlived_its_permission` — so the state is reviewable afterwards, not only at the time.

User turns are not re-authorised: what bob typed carries nothing the system fetched for him.

## Why this is conservative, and why that is right

Losing *any* role the turn was produced under drops it, even if the role lost had nothing to do with
that particular turn. A precise check — "was this specific field visible only to that role?" — would
need the field obligations of every tool recorded with every turn. The conservative check costs some
history after a demotion. The precise one, done wrong, costs the data. In a system where a
demotion is rare and an over-broad replay is invisible, pay the first cost.

## The same control, three times in this lab

| Where | What is re-checked on every use |
|---|---|
| The API (track 1) | roles, from the database, not from the token |
| The worker (track 6) | the approval, against the payload hash, at execution |
| History replay (here) | the roles a stored result was produced under |

Authorisation is not something you pass once. It is something you ask again, where the data is used.
