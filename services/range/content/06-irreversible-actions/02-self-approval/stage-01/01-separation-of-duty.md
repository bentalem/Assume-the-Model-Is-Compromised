# Separation of duty

The oldest control in this course, and the one that survives the most.

> **The person who asks for a thing may not be the person who approves it.**

It is older than computers. Two signatures on a cheque, a second pair of eyes on a prescription, the
person who counts the cash not being the person who banks it. It works because it does not depend on
anybody being trustworthy — it depends on **two people having to be wrong at the same time**, which
is a different and much better bet.

## Why it belongs in a course about agents

Because an agent collapses roles that used to be held apart by the fact of being different people.

The agent raises the refund. The agent has the context to justify it. If the agent can also approve
it, then everything downstream of the approval is decided by one component that is steerable by a
customer's ticket text.

And notice what separation of duty does that a permission check does not: an injection that
successfully talks the agent into proposing a fraudulent refund **still has to get past a person who
did not read the ticket.** The control does not care how the request was produced. That property —
indifference to how convincing the request was — is exactly what you want against an attacker whose
whole technique is being convincing.
