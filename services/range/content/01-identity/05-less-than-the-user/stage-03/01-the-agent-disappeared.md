# The agent disappeared

## What your result proves

Unarmed, three rows:

```
status-helper reads the order      minted: act=status-helper; scope=orders:read    200
status-helper reads a customer     none: refused by the broker before minting      403 scope_exceeds_profile
alice reads the customer directly  the user's own token, no act                    200
```

The second request never reached the API. The broker resolved the operation from the method and path — `GET /v1/customers/{customer_ref}` is `customer.read`, which needs `customers:read` — and `status-helper`'s ceiling is `orders:read`. Nothing about alice was consulted, because nothing about alice needed to be: the agent was asking for something its task does not include.

Armed, the second row reads `passthrough: the user's own token, no act`, the status is 200, and `revealed` holds a customer's email. That is your flag, and it is data alice was always allowed to see. **The agent was not.**

Now read the audit observation. The minted order read says `person: Alice Nguyen, agent: status-helper`. The passthrough customer read says `agent: (none: the user alone)` — exactly the same as alice's own direct read. Afterwards, nobody can tell those two apart. One of them was alice. The other was an agent that may have been following instructions from a ticket.

> Passthrough does two things at once: it hands the agent everything the user can do, and it removes the agent from the record of what was done.

## Where the control lives

In the broker's gateway, before a token exists (the first source panel):

1. the operation is resolved from **method and path**, never from a body or anything the model wrote;
2. the scope it needs comes from `scopes.json` — the same file the policy loads, so the broker and the policy cannot disagree;
3. the profile's ceiling is checked, and a call outside it is refused with `403 scope_exceeds_profile`;
4. a token is minted for **exactly that one scope**, for 60 seconds, naming alice as `sub` and the profile as `act`.

The API then records both. `actor_type` stays `user` and `actor_id` stays alice — the human is still the actor — and migration `0030` adds `agent_id` beside them (the third panel). Passthrough leaves that column empty, which is the whole of failure 7: *`act` lost in the audit.*

The second panel is the armed branch, and it is worth looking at how small it is. A real deployment gets there with one setting and a comment saying it is temporary.

## What restoring fixes

Restoring puts the broker back to minting. The customer read through status-helper is refused again, and the next rows in the trail name the agent again.

It does not repair the rows written while it was armed. Those customer reads are in the trail as alice, alone, for good — the trail is append-only, and it cannot record a party it was never told about. If an injection had used that window, the investigation would find alice reading customers and nothing to say she did not.

## Take it to a review

1. **"When your agent calls a tool, whose token is on the call — and what can that token do that the task does not need?"** If the answer is "whatever the user can do", that is passthrough, however the request is routed.
2. **"Does the agent's token name the agent?"** Ask to see an audit row for an agent action. If it names only the user, attribution is gone before anything goes wrong.
3. **"Who decides the scope — and from what?"** From the operation and a table somebody reviewed, or from what the agent asked for? Challenge 1.7 is the second answer.
4. **"How long does the agent's token live, and does it outlive the task?"** A refresh token handed to an agent is authority left lying around.
5. **"Is there a passthrough mode, and who can turn it on?"** It usually exists, it is usually called a fallback, and it is usually still on.

Question 5 is the one that finds things. The narrowing is rarely missing; it is disabled, for a good reason, a while ago.

**Restore before you leave.** Until you do, every call through the broker carries alice's whole token.
