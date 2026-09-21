# Per call, per session

This challenge has no exploit in it. Nothing is armed, no control is removed, no token is tampered
with, and no instruction is hidden in anything. Every request you are about to make is one the
system is built to allow, made by a real support agent with a real role, inside every limit the
policy sets.

That is the challenge. **The finding is what the permitted requests add up to.**

## The control that exists

Search is bounded, and properly. The policy returns a page size with the decision:

```
"max_results": 25
```

The API clamps to it — the lowest of what the caller asked for, the endpoint maximum, and the
policy obligation wins. A caller asking for `limit=50` gets 25. That is not decoration: the field
list is bounded the same way, and `email` is not in it.

So one call is bounded, deliberately, in two dimensions at once. Anyone reviewing this tool in
isolation would pass it, and they would be right to.

## The control that does not exist

Now ask the next question, which almost nobody asks:

> **What bounds the second call?**

Nothing. There is no per-session total, no per-user quota, no counter of any kind. The response
carries a cursor, and the cursor is how pagination is supposed to work — a tool that returned
twenty-five records with no way to see the twenty-sixth would be broken.

So the caller asks again with the cursor. And again. Each call is inside the cap. Each is
authorised. Each is logged as `allowed`, correctly, because each one *is* allowed.

| | Bounded | By what |
|---|---|---|
| records per call | yes | the policy obligation, clamped by the API |
| fields per record | yes | the policy obligation, applied before the response is built |
| calls per session | **no** | nothing |
| depth of paging | **no** | the cursor advances until the data runs out |
| minimum query length | **yes, and it does not help** | the schema says `minLength: 2`, and `ar` is two |
