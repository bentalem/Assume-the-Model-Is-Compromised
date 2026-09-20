# It changed mid-session

`email` stopped coming back.

```
before   customer_ref, full_name, assigned_team, open_ticket_count, email
after    customer_ref, full_name, assigned_team, open_ticket_count
```

Same person. Same endpoint. Same customer. **Same token** — nothing reissued it, nothing invalidated
a session, and nothing asked bob to log in again.

The only thing that changed is one column in one row of `app.memberships` — `support_manager`
became `support_agent` — and the next request read it.

## What the API did, in order

```
1  verify the token          signature, issuer, audience, expiry     unchanged
2  read the subject          the `sub` claim                          unchanged
3  load the memberships      SELECT ... FROM app.memberships          CHANGED
4  build the policy input    subject.roles from step 3
5  ask the policy            restricted customer, not a manager
6  apply the obligation      a narrower field list
```

Steps 1 and 2 are the token's job and the token did them perfectly. **Step 3 is where authorization
attributes come from**, and it is a query, not a claim.

Had the roles been read from the token, step 3 would not exist. Steps 4 to 6 would have run on a
snapshot taken at login, and bob would have kept seeing the email address until his token expired —
with nothing anywhere logging that anything was wrong, because from the system's point of view
nothing was.

## The demonstration is the absence of an event

Worth sitting with, because it is the unusual shape of this challenge.

Nothing was denied. No alarm, no 403, no audit row saying "revoked user attempted access". Bob's
request succeeded, in both cases, with a `200`.

The control expressed itself entirely as **a field that was no longer there**, and if you had not
written down the first field list you would not have noticed. That is what a correctly working
authorization layer usually looks like: not a refusal, but a smaller answer, arriving without
comment.

## What to ask, and what the answers mean

> **"A user's role is revoked. How long until the system stops honouring it?"**

If the answer involves token lifetime, follow up with:

> **"Show me one request. Where do the roles in the authorization decision come from?"**

And then the one that settles it, because it needs no access and no trust:

> **"Revoke a role and make the same request again, now, while I watch."**

That is what you just did. It takes about forty seconds and it cannot be argued with.

## Writing it up

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

The last sentence is the one worth keeping, and it is the general form of everything above:

> **Identity comes from the token. Permissions come from the server, loaded fresh, every request.**

**Reset before you leave.** Bob is currently not a manager, and the next thing you measure will be
measuring that.

---

*A note on how this challenge was built. The first version revoked bob's membership outright. It is
his only one, so revoking it removed him from the tenant and the next request came back `404` —
refused by the resource lookup before policy was consulted. True, interesting, and not this lesson:
a 404 shows that something changed, while a narrowed field list shows exactly what. The content had
been written before the mutation was run end to end, and described an outcome nobody had observed —
which is the same error as a test named for a claim it does not check.*
