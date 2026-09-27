# Reading history is an access decision

The database policies on `mem.sessions` and `mem.turns` normally allow only the owner to read a conversation.

When `history.org_readable` is enabled, a manager may also read a colleague's transcripts **within the same organisation**. The service records whether the read was made as the owner or under the review setting.

The setting does not expand write access. A manager still cannot add turns to another user's session, and another organisation remains blocked.

Without review access, the service does not confirm that a colleague's session exists. A hidden session and an unknown session both appear unavailable to the caller.

## Take it to a review

- Which roles can change the history review setting?
- Does review access include old tool results fetched with another person's rights?
- Does the audit log show who read the transcript and why?
- Can review access be granted without also granting write access?
