# Why an agent changes the stakes

Be precise about this one, because overstating it is how a report loses the engineers in the room.

> **Row-level security is not an agent control.** It is ordinary multi-tenancy engineering, it
> predates all of this, and a system with no agent in it needs it just as much.

If you find this gap in a client's system, write it up as what it is: a tenant isolation finding.
Calling it an AI risk costs you credibility with the people who have to fix it, and they will be
right.

So why is it track 2 of a course about securing agents?

## Because it is the layer that makes an agent's mistakes survivable

In a conventional application the set of queries is finite and written by hand. Every one of them
was typed by a person who could be asked about it. Application-level filtering is *nearly* enough,
because "nearly" means "one query in five hundred", and code review catches most of those.

An agent breaks all three of those assumptions at once:

**The query paths explode.** The agent composes calls at run time in combinations nobody enumerated.
You cannot review the list of queries, because there is no list.

**The caller is steerable by data.** A conventional caller does what the code says. An agent does
what the code says *plus whatever the ticket it just read said*. The thing choosing which record to
ask for is influenced by content an attacker wrote.

**Tools accumulate.** Every quarter adds two more. Each one is reviewed on its own, and the
interaction between them is reviewed by nobody.

Against that, a control enforced by *remembering* is not a control. A control enforced by the
engine is.

## The one-line version

> **Row-level security does not stop an agent from doing the wrong thing. It decides whether the
> wrong thing reaches another tenant's data.**

Which is why it is worth an afternoon: it is the cheapest layer you will ever add that keeps holding
after everything above it has been talked into something stupid.

## And the classification matters in the write-up

Most of agent security is not new. Identity, authorization, tenant isolation, audit, secrets —
things the industry knows how to do, applied at a boundary that happens to be new. The genuinely new
parts are narrow: untrusted input that is also control flow, tools as ambient authority,
non-determinism.

A reviewer who can tell those apart writes findings engineers act on. A reviewer who labels
everything "AI risk" writes findings engineers stop reading.
