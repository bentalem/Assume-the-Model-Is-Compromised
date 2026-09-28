# What you are about to run

## The attempt

The probe plays a compromised `status-helper` again, this time asking the broker directly for more:

1. It authenticates to the broker's exchange endpoint as `status-helper`, with the profile's credential.
2. It presents alice's token and asks for `customers:read`.
3. If a token comes back, it reads a customer with it: `CUS-4003`.

`status-helper`'s ceiling is `orders:read`. alice, a support agent in cedar, may read customers. So the request is inside what the user may do and outside what the agent may do. Which of those two decides is the whole challenge.

## The switch

**Bound an agent's requested scope only by the user** is a real configuration, usually called something like *agent-requested scopes, auto-approved*. With it armed, the broker checks a requested scope against every scope it knows — except approval, which it never mints — rather than against the profile's ceiling.

The broker does not know alice's roles and does not need to: the API loads them from the database on every call. So with the switch armed, the only limits left are the user's roles and the approval rule.

## What to read

- The **status** and **error code** unarmed. A 400 from the broker is a different answer from a 404 from the API.
- The **token** column and **last token** armed: what scope was minted, and for whom.
- The **reason** on the audit row for the customer read, armed. It says which rule shaped what came back — and it is not the agent's ceiling.

`CUS-4003` is a restricted customer. Remember what challenge 3.2 showed about restricted customers and support agents before you read the answer.
