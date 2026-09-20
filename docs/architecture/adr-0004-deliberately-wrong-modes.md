# ADR-0004 — Arming a control, and building a broken one, are different things

**Status:** accepted
**Decides:** challenge 3.4, and the general question of what the Range may make the lab do.

## The conflict

`.dev/ctf/design.md` §5 lists two capabilities the Range needs:

> **A deliberately wrong policy-fallback mode** — deny-on-outage can only be *seen* as a choice if
> the other choice can be switched on.
>
> **A togglable request-context mode** — `SET` vs `SET LOCAL` is a two-line difference and a whole
> class of bug.

`CLAUDE.md` lists, under *"Never fix a failing environment by weakening a control"*:

> - disable row-level security, or grant `BYPASSRLS`
> - **add a cached or fallback allow path for when OPA is unavailable**

So the design document asks for a thing the build rules prohibit. That is worth resolving in
writing rather than by whichever file the author happened to read last.

## Why the existing mutations are not already a violation

`rls.orders.disable` disables row-level security, which is the first item on that list. It has been
shipped, and this ADR should explain why that was not a breach before it decides anything else.

The rule prohibits **accepting** a weakened control — leaving it weakened because something did not
work otherwise. The Range does the opposite:

| | Arming, in the Range | What the rule prohibits |
|---|---|---|
| Duration | seconds, with a proven inverse | indefinite |
| Purpose | to observe the consequence | to make something work |
| Visibility | the console says *armed*, loudly | silent |
| Verification | `verify_local.py` and the migration smoke test **fail while armed** | passes, because the check was removed |

The last row is the strongest part of the argument. Arming a control in this lab makes the
verification suite go red. That is not a system that has accepted a weakened control; it is a system
that notices immediately, which is what the rule is protecting.

**The general principle:** *changing a configuration value to its wrong setting, reversibly, while
every check screams, is a demonstration. Removing a check so that something passes is the thing the
rule forbids.*

## Where that reasoning stops

It does not extend to writing the broken behaviour into the code.

A fallback-allow path in the API is not a setting at its wrong value. It is **a code path that does
not otherwise exist**, added to the service the lab is modelling, which would then be shipped in
every image, present in every review, and one environment variable away from being live.

That failure has a name and the lab teaches it: a debug mode nobody meant to enable. Track 9 is
about what the runtime may change about itself, and a repository arguing that case cannot also
contain a switch that turns its own authorization off.

The asymmetry is worth stating plainly:

> **Arming a control the system already has is a demonstration. Adding a control path that fails
> open is a vulnerability with a comment above it.**

## The decision

**3.4 will not be built by adding a fallback mode to the API.** The API keeps exactly one behaviour
when OPA is unreachable, and `V-09` proves it.

3.4 is instead **deferred**, and the honest reason is recorded here rather than dressed up: the lab
can show that deny-on-outage *is* the behaviour — challenge 3.1 does that, by stopping the engine
and reading the trail — but it cannot show the alternative without becoming a system that has the
alternative.

If 3.4 is built later, the two acceptable shapes are:

1. **A separate, disposable service** that demonstrates the wrong behaviour, never on the `app`
   network, never the real API. The learner sees a fallback-allow, and the API never contains one.
2. **Source reading.** Stage 01 shows what the code would look like, from a file that is not
   installed anywhere, with the test that would catch it.

Both are weaker than arming a switch, and both are the right kind of weaker.

## The same reasoning applied to 2.2

The context-mode capability — `SET` versus `SET LOCAL` — falls the same way and is worth checking
against the principle rather than assumed.

`SET LOCAL` on a pooled connection is not a control the system has, set wrongly. Making it togglable
means the API gains a code path that leaks request context between users, which is the
vulnerability the lab exists to warn about, living in the lab's own API.

**Deferred, on the same grounds, with the same two acceptable shapes.**

## What this costs, said plainly

Two challenges out of thirty, and they are good ones. The cost is real.

The alternative cost is a repository that teaches people to ask *"what can your runtime turn off
about itself?"* while carrying two switches that turn off its own authorization and its own tenant
isolation. That is a worse trade, and it would be the first thing a graduate of this course should
find.
