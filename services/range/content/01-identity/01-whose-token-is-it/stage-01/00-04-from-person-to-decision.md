# Part 3: from a person to a decision

The API now knows who is asking and where they belong. It still does not know **which tenant this request is about**. That comes from the record being asked for, not from the person and not from the request.

## The exact order

For a request such as `GET /v1/orders/ORD-2001`:

1. **Verify the token** and read `sub` (Part 1).
2. **Load the person** and their active memberships (Part 2).
3. **Load the record.** The order number is looked up **once per tenant the person belongs to**, each time inside that tenant's own database context, so row-level security applies to every lookup. A tenant the person does not belong to is never queried at all.
4. **If nothing was found**, the answer is `404` — the same answer whether the order does not exist or belongs to another tenant. The audit row records `resource_not_visible`.
5. **Ask the policy.** The input includes the person's roles **in the record's tenant** — not their roles anywhere else. For a delegated token it also includes the agent and the token's scope, and the policy refuses anything the scope does not cover (1.6).
6. **Query and trim.** The policy can allow the read and still remove fields. A support agent reading a restricted customer gets fewer fields than a manager does.
7. **Write the audit row.** It names the person loaded in step 2 as the actor, and — for a delegated token — the agent chain beside them in `agent_id`.

Example of what alice's two reads look like from the inside:

```text
alice -> ORD-2001   her tenants: cedar   found in cedar       -> policy asked -> 200
alice -> ORD-3001   her tenants: cedar   not found in cedar   -> 404, policy never asked
```

Northwind was not searched in the second request. There was nothing for alice to learn about it, not even whether ORD-3001 exists.

## What this means for an agent

The model sees none of these steps. It sees tools such as `get_order`, whose inputs are an order number and two yes-or-no options. It has no field in which to name a user, a tenant or a role — so the most it can do is ask for a record, and everything above decides what that request is worth.

That makes the **credential on the call** the single most important choice in the system. Whatever identity the token names is the identity every step above works for — and, from 1.5 on, whatever limit the token carries is the most of that identity the agent can use.

## Which challenge tests each part?

| Challenge | The question you will answer |
|---|---|
| 1.1 | What changes when the agent carries its own credential instead of the user's? |
| 1.2 | Does the API accept a genuine token that was issued to a different service? |
| 1.3 | When a role is removed in the database, how soon does the API stop honouring it? |
| 1.4 | What does a forged or rewritten token achieve, and where is it stopped? |
| 1.5 | How much of the user's authority does the agent need — and who can tell afterwards that it acted? |
| 1.6 | A token narrowed correctly: does anything read the narrowing? |
| 1.7 | Who decides an agent's scope — and what is left when the agent does? |
| 1.8 | When an agent hands its token on, can the chain grow? |

**Now start challenge 1.1.** You will send the same two requests with two different credentials and compare every row.
