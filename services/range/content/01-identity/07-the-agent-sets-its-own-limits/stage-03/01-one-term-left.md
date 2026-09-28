# One term left

## What your result proves

Unarmed:

```
token: none: the broker refused. status-helper asked for customers:read     400 scope_exceeds_profile
```

The broker refused at the exchange, so no token existed and the API was never asked. The limit that held was the **agent's ceiling**: `customers:read` is not in `status-helper`'s profile.

Armed:

```
token: minted: act=status-helper; scope=customers:read     200    revealed: <a name>
audit: customer.read  allowed  restricted_customer_minimal_fields  agent: status-helper
```

The broker minted exactly what the agent asked for. The ceiling is still written in the profile file; it just stopped being the thing a request is checked against.

Now look at what came back, and the reason on the audit row. `CUS-4003` is restricted, and alice is a support agent, so the policy's field obligation removed the contact details. The agent got a name and not an email. **The user's term still held.** Roles come from the database on every request, and no token — narrow, wide, or minted on request — changes that.

That is the formula with its middle term gone:

```
effective permission  =  what the user may do  ∩  whatever the agent asked for
```

The only thing between an injected agent and the user's whole reach is now the user's reach.

## Where the control lives

In the broker's exchange, in one line (the first panel): which set a requested scope has to fit inside. Secure, that is the profile's ceiling, loaded from a reviewed file when the broker starts (the third panel). Armed, it is every delegable scope in the table.

Two things sit outside that line and hold in both states:

- **Approval is never minted** (the second panel), whatever the switches say. And the policy refuses a delegated `refund.approve` with `agent_cannot_approve` even if a token carrying the scope reached it — the ceiling at the resource server, not only at the issuer.
- **The API's own checks** — the user's roles, the tenant, row-level security — never read the broker's settings at all.

What decides the third term — what *this task* needs — is the gateway's operation-to-scope table. An agent using the exchange endpoint names the scope itself, which is why the exchange has to check it against something the agent did not write.

## What restoring fixes

Restoring puts the ceiling back as the bound. The same request is refused at the broker again, before a token exists.

Tokens already minted while it was armed are not recalled. They live at most five minutes and never longer than alice's own token, which is exactly why the lifetime is short: a mistake in what was minted expires on its own.

## Take it to a review

1. **"Who chooses the scope of the agent's token?"** If the answer is the agent — or the model, through a tool argument — the ceiling is whatever an injection asks for.
2. **"Where is each agent's ceiling written, and who can change it?"** It should be configuration an administrator reviews, not a parameter.
3. **"If an agent asks for more than its ceiling, what happens?"** Refused, or approved because the user could do it? The second is passthrough with extra steps.
4. **"What can no agent ever be given?"** There should be a list, it should be short, and it should be enforced where the data is as well as where the token is minted.

Question 1 is the one that matters. Everything else in this track assumes the answer is *trusted code*.

**Restore before you leave.** Until you do, any agent can obtain any scope alice has, except approval.
