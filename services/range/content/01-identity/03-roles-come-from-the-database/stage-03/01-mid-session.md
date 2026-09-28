# It changed mid-session

## What your result proves

`email` stopped coming back.

```
before   assigned_team, customer_ref, email, full_name, open_ticket_count
after    assigned_team, customer_ref, full_name, open_ticket_count
```

Same person. Same endpoint. Same customer. **Same token** — nothing reissued it, nothing invalidated a session, and nothing asked bob to log in again. The only thing that changed is one column in one row of `app.memberships` — `support_manager` became `support_agent` — and the next request read it.

### The demonstration is the absence of an event

Nothing was denied. No alarm, no 403, no audit row saying "revoked user attempted access". Bob's request succeeded, in both cases, with a `200`.

The control expressed itself entirely as **a field that was no longer there**, and if you had not written down the first field list you would not have noticed. That is what a correctly working authorization layer usually looks like: not a refusal, but a smaller answer, arriving without comment.

## Where the control lives

What the API did, in order:

```
1  verify the token          signature, issuer, audience, expiry     unchanged
2  read the subject          the `sub` claim                          unchanged
3  load the memberships      app.resolve_subject(sub)                 CHANGED
4  build the policy input    bob's roles in the customer's tenant
5  ask the policy            restricted customer, not a manager
6  apply the obligation      a narrower field list
```

Steps 1 and 2 are the token's job, and the token did them perfectly. **Step 3 is where authorization attributes come from**, and it is a query, not a claim. It is line 64 of `dependencies.py` — `load_subject` — and it runs on every request, with no cache in front of it.

Steps 5 and 6 are track 3's subject: the policy allowed the read and returned an **obligation** to remove fields a support agent may not see.

Had the roles been read from the token, step 3 would not exist. Steps 4 to 6 would have run on a snapshot taken at login, and bob would have kept seeing the email address until his token expired — with nothing anywhere logging that anything was wrong, because from the system's point of view nothing was.

## What restoring fixes

Restoring sets bob's membership back to `support_manager`, and the very next request returns the email again. No token changes in either direction. The API keeps no copy of what bob was shown, so there is nothing left behind to clean up.

That last sentence is only true of the API. Anything that **stored** bob's answers — a chat history, a cache, an export — still holds the email he saw as a manager. Challenge 9.4 is this challenge with a memory in the way.

*Why a demotion and not a removal.* Bob has one membership, so removing it would take him out of the tenant entirely and the next request would come back `404` — refused by the resource lookup before policy was ever consulted. True, and a different lesson: a `404` shows that something changed, while a narrowed field list shows exactly what changed and where the narrowing happened.

## Take it to a review

> **"A user's role is revoked. How long until the system stops honouring it?"**

If the answer involves token lifetime, follow up with:

> **"Show me one request. Where do the roles in the authorization decision come from?"**

And then the one that settles it, because it needs no access and no trust:

> **"Revoke a role and make the same request again, now, while I watch."**

That is what you just did. It takes about forty seconds and it cannot be argued with.

```
Authorization roles are read from the access token rather than from the server on
each request. A role revoked in <system of record> continues to be honoured until
the user's token expires — currently <N>, and up to <M> where refresh tokens are
in use.

Demonstrated: <role> revoked at <time>; the same token continued to receive
<capability> until <time>.

Fix: load authorization attributes per request from the system of record. The token
establishes identity; it should not establish permissions.
```

> **Identity comes from the token. Permissions come from the server, loaded fresh, every request.**

One refinement arrives in 1.5: a token minted for an agent carries a `scope`. That does not break this rule, because the scope is a **limit** on what the server loaded, never a source of it. Demote bob and his agent loses the email too; give his agent a wider scope and bob still sees only what his role allows.

**Reset before you leave.** Until you do, bob is not a manager, and the next thing you measure will be measuring that.
