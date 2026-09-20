# One header value

When an agent calls a tool, something goes in the `Authorization` header. There are three
possibilities, and which one you chose constrains everything else you will ever do about security in
that system.

| | What is in the header | If the model is steered |
|---|---|---|
| **A** Service account | the agent's own credential | the union of every user's permissions |
| **B** Service account plus claimed user | the agent's credential, user id as a parameter | the same, and it *looks* like per-user access control |
| **C** Passthrough | the signed-in user's own token | what that one user already had |

## Why A needs to be so wide

This is the part people hear as criticism and it is arithmetic.

A single credential that answers for **every** user must be able to reach **everything any of them
could reach**. If it cannot, some user's request fails. So the breadth is not carelessness in the
implementation — it is the requirement, and there is no narrower version of it.

In this lab that means membership in cedar *and* northwind, as a manager in both. When you arm the
control you are not introducing a bug. You are configuring a service account correctly.

That is what makes it worth an afternoon: **the vulnerability is the architecture working as
designed.**

## Why B is the dangerous one

Because it looks like C.

The tool takes a `user_id` parameter. The logs show per-user access. The code reads as though it
checks permissions per user. A review passes.

But the model produces that parameter, and anything the model produces is influenced by whatever the
model just read. The credential is still the wide one; the only thing standing between a customer's
ticket text and another tenant's data is a string the model chose.

> If a tool argument contains `user_id`, `organization_id`, `role` or `approved`, **the field should
> not exist.** Identity comes from a verified token, never from an argument.

## When a service account is the right answer

It is not always wrong, and saying so is how you keep credibility.

There are cases with no user at all — scheduled jobs, queue watchers, reconciliation — and cases
where the downstream system has no way to accept a user token. The usable rule is:

> **Service identity for anything that makes no access decision about user data. User identity for
> everything that does.**

And when passthrough is genuinely impossible, in order of value:

1. Put the decision in a service that *does* know the user, and let it call the legacy system with
   the service credential. A service key is only a problem in the hands of something that does not
   know who the user is.
2. One credential per tool, not per agent.
3. One credential per tenant, not one globally.
4. **Record the initiating user in the audit trail even when enforcement cannot use it.** Losing
   enforcement is bad; losing the ability to say who asked is worse.
5. Volume caps, approval for anything high-impact, monitoring per initiating user.

## What you are about to run

Four requests, twice. alice asking for her own order and for the other tenant's; the agent's own
account asking the same two.

Run all four **before** arming anything, and write down what you get. Then configure the service
account and run them again.

Watch what changes and, more importantly, what does not.
