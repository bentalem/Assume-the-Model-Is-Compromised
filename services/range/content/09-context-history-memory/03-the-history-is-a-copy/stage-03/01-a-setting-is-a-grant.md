# A setting is a grant

The decision chain for bob's read:

1. **Identity** from bob's verified token; organisation and roles from the core database, per request.
2. **Row-level security** on `mem.sessions` and `mem.turns` decides visibility. The policy allows the owner — or, when `history.org_readable` is true, a `support_manager` in the same organisation.
3. **The service records how the read was allowed**: `owner` or `org_readable_manager`. A read by the organisation is visible in the audit trail as exactly that, never as an ordinary read.
4. **Writing is never widened.** Even armed, bob cannot append to alice's session, and mallory — in another organisation — cannot read it at all. Both are checked by the lab's live suite.

Unarmed, bob's request was not refused as "forbidden". The session simply was not visible to him —
the same answer as a session that does not exist. That is deliberate, and it is the same rule the API
applies to another tenant's order: a refusal that confirms existence tells the caller something.

## What the setting actually changed

Nothing in the service's code. One row in `mem.settings`, read by a policy. Which is the lesson:
**the access control for history was a configuration value**, and whoever can change configuration
can change who reads every conversation the agent has had. In a real product that is a settings page.
Treat it like a grant — reviewed, recorded, and scoped — because it is one.
