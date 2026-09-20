# One of them did nothing

That is the finding, and it is worth saying in the order you discovered it.

## Removing the tenant check changed nothing

The policy now permits any support role to read an order in any tenant. You can see it in the bundle
state, and the policy's own test suite fails the two tests that cover it. And the cross-tenant read
returns exactly what it returned before: `404`, with the audit row reading `resource_not_visible`
and **no policy version**.

Nothing was returned because nothing was asked. The request was refused at the resource load, by
row-level security, before the policy engine was reached at all. The permissive rule you installed
was never evaluated.

So for tenant isolation the two layers are not equal partners. **The database is the control, and
the policy is agreeing with it afterwards.** You could remove the tenant condition from the policy
entirely and this system would still be tenant-isolated — which is a genuinely reassuring thing to
know, and you only know it because you tried.

## Removing the role check returned data

Same file, same action, one condition further down. fiona is a `finance_approver` in this tenant.
She approves refunds; she has no role that reads orders. Unarmed, she gets a denial with a reason
and a policy version — the engine refused her, and said so.

With the role check removed she gets `200`, and the order fields come back.

There is no second layer underneath. Row-level security looked at that row, saw it belonged to her
tenant, and returned it, because that is the only question it knows how to ask. Nothing else in the
request path has an opinion about what a `finance_approver` may read.

## The asymmetry, stated plainly

| Removed | Second layer | Outcome |
|---|---|---|
| the tenant check | row-level security | **nothing happened** — the policy was never asked |
| the role check | nothing | **data returned** to someone who should not have it |

> A policy bug costs you nothing for the properties something else also enforces, and everything for
> the properties only the policy enforces. **The severity of a policy bug is not a property of the
> policy.**

That is why "we have defence in depth" is not an answer to "what happens if this rule is wrong". The
right answer names the property and names the second layer, or admits there is not one.

## What this does not mean

It does not mean the tenant condition in the policy is dead weight, and a review that concluded that
would be wrong twice over.

It is what keeps the *decision* correct for anything that does not go through a resource load — a
search, a list, a creation, an action whose resource does not exist yet. And a duplicated control is
how you survive the day the other one is switched off, which is exactly what challenge 2.1 arms. The
layers cover each other precisely *because* they overlap on this one property.

What it means is narrower and more useful: **you cannot know what a control is worth until you know
what is underneath it**, and the only reliable way to find out is to remove it and look.

## Take it to a review

1. **"Which of these rules has a second layer underneath it, and which does not?"** Ask it rule by
   rule. A team that has never asked will not have an answer, and the pause is the finding.
2. **"Show me an audit row for a denial. Does it carry a policy version?"** Then ask what refused
   the ones that do not.
3. **"If this policy file were empty, what would still be enforced?"** The answer is the set of
   properties with a real second layer. It is usually much smaller than people expect.
4. **"What does row-level security actually check?"** Tenant, usually ownership, sometimes state.
   Almost never roles, never fields, never approvals.
5. Then the one that matters: **"So which of your controls is load-bearing on its own?"** Those are
   the ones that need the tests, the review and the alerting.

**Reset before you leave.** If the bundle state says anything other than `correct` for both, the
policy OPA is serving is not the one in the repository, and every measurement you take until it is
matches nothing.
