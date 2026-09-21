# What you will run

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
