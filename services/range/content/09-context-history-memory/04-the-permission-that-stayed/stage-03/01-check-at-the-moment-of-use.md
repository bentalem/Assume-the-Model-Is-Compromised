# Why the old permission reached the next turn

## What your result proves

Bob fetched the restricted customer result while he had the manager role. The runtime saved that result in his history. After Bob was demoted, a new API request no longer had the same access.

With history revalidation enabled, the earlier manager-only turn was **omitted** from the new context. When you disabled revalidation, that saved turn became available again even though Bob no longer held the role.

This needed **two changes**: Bob's role had to be removed, and the memory layer had to stop checking old turns. Demotion alone was not a failure. A replay check that was disabled while Bob still held the role would not show an old permission being used.

## How replay is checked

When the runtime saves a turn, `history.py` stores the user's roles in `authz`. It gets those roles from the verified principal, not from the request body.

When `context.py` rebuilds context, it resolves the user's current roles from the core database. For each old tool or assistant turn, it checks whether the user still has every role recorded at write time. If a role is missing, the turn stays in history but is left out of the new block. The context log records the omission.

## What this check does not cover

This is a broad **role-level** check. It can hide a turn even if the lost role did not matter for that result. It does not know whether the user's access to one specific customer or document changed while their roles stayed the same.

More exact checks would need each saved tool result to record which resource and permissions were required, then check those rights again before replay. The current lab does not implement that finer check.

## Take it to a review

- Does each stored tool result record enough information to check permission later?
- Are current roles loaded when context is built, rather than trusted from an old token?
- What happens when document access is removed without changing the user's role?
- Can an investigator identify which old results were included after a permission change?
