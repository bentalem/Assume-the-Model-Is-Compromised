# The token was right

## What your result proves

Unarmed:

```
token: minted: act=status-helper; scope=orders:read     404 not_found
audit: customer.read  denied  scope_not_granted  agent: status-helper  2026-09-28.1
```

Armed:

```
token: minted: act=status-helper; scope=orders:read     200    revealed: <an email>
audit: customer.read  allowed  same_organization_and_allowed_role  agent: status-helper  2026-09-28.1
```

The token column is identical in both runs, and so is the last-token observation: same issuer, same `act`, same `scope`, same lifetime. The broker did its job perfectly both times. The only thing that changed was whether the resource server read what the token said.

So the value you submitted proves that **the narrowing was never in the token**. It was in the rule that reads the token. Remove that rule and a correctly narrowed token is exactly as powerful as the user's own.

Two details in the rows are worth a second look:

- **Unarmed, the refusal is a 404.** A scope denial follows the same mapping as every other policy denial of a visible resource, so the caller cannot tell "you may not" from "it does not exist". The audit row can: `scope_not_granted`, with the agent named.
- **Armed, the allowed row carries the same policy version as the real policy.** The version is a literal written inside the rules file, and removing one condition did not change it. That is challenge 3.3's blind spot again: an investigator reading this row sees an allowed decision by the current policy, with nothing to say the rules that made it were not the reviewed ones.

## Where the control lives

In the policy, at the resource server — and in one place for every action (the first two panels).

`scope_granted` asks whether the scope this action needs is in the token. `delegation_permits` requires it for any request carrying a delegation. And `allow_with`, which builds every allow in the policy, allows only when `delegation_permits` holds. So the scope is **a limit, never a grant**: it can turn an allow into a deny and nothing else. Every deny arm is untouched by it. A delegated request refused by tenant or role is still refused for that reason, and roles still come from the database.

```
effective permission  =  what the user may do  ∩  the token's scope
```

The third panel is where the scope reaches the policy: the pipeline builds `delegation` from the verified token, and only for a delegated one. A user's own token reaches the policy through exactly the call it always made.

Two layers still stand behind this one. The ceiling on approval (`agent_cannot_approve`) is a separate condition that the armed variant leaves in place. And row-level security still confines alice to her own tenant — the armed read reached a cedar customer, never a northwind one.

## What restoring fixes

Restoring puts the real policy back and restarts OPA. The same token is refused again, with the same reason, and nothing about the broker had to change — which is the point.

It does not undo the read. The trail records it as allowed, with the agent named — at least the agent is there this time — under a policy version that does not admit the policy was different.

## Take it to a review

1. **"Where is the token's scope enforced?"** Ask for the line of code. "The gateway narrows it" is an answer about minting.
2. **"What happens if the agent calls the service directly?"** If the only enforcement is in the path the agent is supposed to use, the agent can use a different path.
3. **"Show me a request with a valid token for the wrong scope being refused."** Not a missing token, not a forged one — a genuine token used for something it does not cover.
4. **"Is the scope a limit or a grant?"** A policy that allows *because* of a scope has handed authority to whoever issues tokens. One that only denies *without* it has not.

Question 3 is the one that finds this. Every test suite has the forged-token case. Very few have the right-token-wrong-use case, and that is the one a compromised agent produces.

**Restore before you leave.** Until you do, the API ignores the scope of every delegated token.
