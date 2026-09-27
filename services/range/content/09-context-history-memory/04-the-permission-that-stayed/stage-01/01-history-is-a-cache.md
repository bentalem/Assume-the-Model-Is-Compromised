# Old history can outlive an old permission

Suppose a manager uses a tool to read a restricted customer record. The runtime saves the tool result in history while that manager has the required role.

Later, the manager loses that role. The main business API checks current permissions, so a new request would no longer return the same restricted data. But history already contains the old answer.

```text
09:00  Manager fetches restricted record
09:01  Runtime saves tool result and roles at write time
10:00  Manager role is removed
10:05  Runtime tries to replay the old turn
```

## The check you built

The saved turn has an `authz` field containing the roles held at write time. Context assembly checks the user's current roles again. If they lost a recorded role, it leaves out that tool or assistant turn.

This is a broad role check; it does not track permission changes to individual fields or records.

## Your task

Observe the replay before demotion. Then remove the manager role and observe it again. Finally disable history revalidation and see what reaches the context.

The old record was allowed **when it was fetched**. The question now is whether it is still allowed **when replayed**.
