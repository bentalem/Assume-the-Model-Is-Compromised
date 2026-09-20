# "We have two layers"

Everyone says it. Almost nobody can say **which layer stops which thing**, and that is the whole
difference between defence in depth and two controls that happen to be in the same request.

This system really does have two: a policy engine the API consults on every call, and row-level
security in the database underneath it. That is invariant 4 of the lab, and it is not decoration.

But "two layers" is a claim about *coverage*, and coverage is per-property:

| Property | Can the policy express it | Can row-level security express it |
|---|---|---|
| this row belongs to another tenant | yes | **yes** |
| this role may not read orders | **yes** | no |
| only these fields may be returned | yes | no |
| this action needs an independent approver | yes | no |

Read the second column. Row-level security is a rule about *rows*. It knows which tenant a row
belongs to, because that is a column. It has no idea what a role is allowed to do, because that is
not a property of the row — it is a property of the request.

So the honest version of the sentence is:

> **One property has two layers. The rest have one.** Which one is which is a question with an
> answer, and if nobody on the team knows it, nobody knows what a policy bug costs.

## The experiment

The way to find out is not to read the policy. It is to remove a check and see whether anything
happens — which is what the two controls on this challenge do.

Both of them edit the same action, `order.read`, in the live policy. Both are derived from the real
policy file rather than from a copy kept somewhere, so what gets loaded is genuinely your policy
with one condition removed. One condition, one action, nothing else touched.

**Run them one at a time**, and restore between. They write the same file, so arming the second
while the first is armed leaves the first reading `unknown` — which the console will tell you.

## What to record for each one

Before you arm anything, run the two reads unarmed and write down what you get. Then for each
removal:

1. What does the request return — status, and any fields?
2. What does the audit trail say: the decision, the reason, and **the policy version**?
3. Did anything reach the caller that should not have?

Question 2 is the one people skip, and it is the one that answers this challenge.
