# One of them did nothing

## What your result proves

That is the finding, and it is worth saying in the order you discovered it.

**Removing the tenant check changed nothing.** The policy now permitted any support role to read an order in any tenant. And the cross-tenant read returned exactly what it returned before: `404`, with the audit row reading `resource_not_visible` and **no policy version**. Nothing was returned because nothing was asked. The request was refused at the resource load, by row-level security, before the policy engine was reached at all. The permissive rule you installed was never evaluated.

**Removing the role check returned data.** fiona is a `finance_approver`. She approves refunds; she has no role that reads orders. Unarmed, she got a denial with a reason and a policy version. With the role check removed she got `200`, and the order fields came back. There is no second layer underneath: row-level security saw a row in her own tenant and returned it, because that is the only question it knows how to ask.

| Removed | Second layer | Outcome |
|---|---|---|
| the tenant check | row-level security | **nothing happened** — the policy was never asked |
| the role check | nothing | **data returned** to someone who should not have it |

> A policy bug costs you nothing for the properties something else also enforces, and everything for the properties only the policy enforces. **The severity of a policy bug is not a property of the policy.**

## Where the control lives

In the **order of work** in `pipeline.py`: the record is loaded — under row-level security, in the caller's own tenants — *before* the policy input is built. If the load finds nothing, the pipeline records `resource_not_visible` and refuses without asking OPA. That ordering is why tenant isolation has two layers and the role check has one.

The three arms of `order.read` in `authz.rego` are the other half: an allow for a member with a read role, a deny for a non-member, a deny for a member with the wrong role. Only the last one has nothing underneath it.

The modified bundles themselves come from `policy_bundle.py`, which derives them from the real policy file at the moment you arm — one named condition removed, nothing else touched.

## What restoring fixes

Restoring writes the real policy back to OPA's bundle, and the bundle state reads `correct` again. fiona's next read is refused.

What restoring cannot fix is the trail of what happened while it was armed — and here the trail has a blind spot worth knowing about. fiona's allowed read was recorded with a **policy version of `2026-09-28.1`: the same version as the real policy.** The version is a literal written inside the rules file, and removing one condition did not change it. So an investigator reading that row sees an allowed decision, made by the current policy version, and has no way to tell from the trail that the rules which made it were not the reviewed ones.

> A version string is a claim the file makes about itself. It is not a fingerprint of what the engine actually loaded.

Track 8 returns to that gap: what a system believes it is running, and what it is actually running.

## Take it to a review

It does not mean the tenant condition in the policy is dead weight. It keeps the *decision* correct for anything that does not go through a resource load — a search, a list, a creation — and a duplicated control is how you survive the day the other one is switched off, which is what challenge 2.1 arms. What it means is narrower: **you cannot know what a control is worth until you know what is underneath it**, and the only reliable way to find out is to remove it and look.

1. **"Which of these rules has a second layer underneath it, and which does not?"** Ask it rule by rule. A team that has never asked will not have an answer, and the pause is the finding.
2. **"Show me an audit row for a denial. Does it carry a policy version?"** Then ask what refused the ones that do not.
3. **"If this policy file were empty, what would still be enforced?"** The answer is the set of properties with a real second layer. It is usually much smaller than people expect.
4. **"What does row-level security actually check?"** Tenant, usually ownership, sometimes state. Almost never roles, never fields, never approvals.
5. **"How would you know which rules were loaded when this decision was made?"** If the answer is a version string in the file, ask what changes it.
6. Then the one that matters: **"So which of your controls is load-bearing on its own?"** Those are the ones that need the tests, the review and the alerting.

**Reset before you leave.** If the bundle state says anything other than `correct`, the policy OPA is serving is not the one in the repository.
