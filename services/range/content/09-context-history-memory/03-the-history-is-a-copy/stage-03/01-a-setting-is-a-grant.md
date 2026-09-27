# What the transcript setting granted

## What your result proves

Before manager review access was enabled, Bob could not see Alice's saved conversation. After you enabled it, the read succeeded **as a manager in the same organisation**.

The difference was not the user's token, the model's instructions or the original ticket. It was a change in the database's read policy. The transcript contained data saved from Alice's earlier interaction, so Bob's new access could include tool results that were originally fetched with Alice's rights.

## Where access is enforced

The `history.org_readable` setting is read by the row-level security policies on `mem.sessions` and `mem.turns`. The normal policy permits the owner. The optional review rule permits a support manager to read a colleague's session in the same organisation.

The service also records **why** the read succeeded: as the owner or through manager review. A request for an inaccessible session does not confirm that the session exists. It looks unavailable to the caller.

The setting widens **read** access only. Bob cannot add messages to Alice's session, and a user from a different organisation still cannot read it.

## What this means for a real deployment

History is not just a record of a chat. It can contain information returned by other systems. A transcript reviewer may receive a second copy of information that the original source would not return to them.

The review setting may be useful for a support team, but it must be treated as an access grant: give it to defined roles, record its use, and check the data it exposes.

## Take it to a review

- Who can enable manager review, and is that change logged?
- Does the transcript contain tool results with stricter access rules than the transcript itself?
- Can the team audit each manager's reads without granting them write access?
- Should some tool results be excluded or masked in the review view?
