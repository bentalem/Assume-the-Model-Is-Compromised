# What you measure instead

## No model is in the loop here, and that is fine

This lab runs no language model. There is no conversation to have, and nothing in this challenge
watches what a model says.

That is deliberate rather than a gap. An assertion about what a model did is not evidence: run the
same prompt twice and you get two different tool calls, so "it refused" proves nothing you could
retest tomorrow. A challenge built on "watch it refuse twice" would be teaching a habit that fails
in front of a real reviewer.

The lesson survives the absence, because the lesson was never about the answer. **Assume the model
complied completely.** Then the only remaining question is what it could reach — and that is
readable from the memberships table and the operation list, with no model required.

## What you are measuring instead

Three things, all of them in the panels beside this text:

1. **The caller's memberships.** `identity.memberships` reads `app.memberships` and shows four
   columns — person, role, status, granted. Alice Nguyen has one active row, `support_agent`. Not
   two roles. The organization is not in the panel; the seed puts her in cedar and only cedar, and
   that single row is what `subject.organizations` is built from.
2. **The registered operation list.** `tools.surface` reads the published action document. Seven
   operations, and that is the complete set of things any instruction can ask for.
3. **A permitted request, made properly.** `api.alice.own_order` is alice reading ORD-2001, which
   she may. Compare it with what the override asks for.

The product of the first two is the ceiling. A successful direct injection in alice's session buys
an attacker exactly that and nothing more — which, since the attacker *is* alice, is what she had
before she typed anything.

## The one deployment change that breaks this

The argument above rests on a single assumption: **the agent holds the caller's token.**

Change that — give the agent a service account so it can work when nobody is logged in — and the
ceiling stops being alice's authority and becomes the account's. Now a direct injection is a real
escalation, because the person typing it is borrowing an identity that is not theirs.

Challenge 1.1 is that change, armed and measured. Here, just notice which assumption everything in
this challenge depends on, so that you know what to ask about in a system that is not this one.
