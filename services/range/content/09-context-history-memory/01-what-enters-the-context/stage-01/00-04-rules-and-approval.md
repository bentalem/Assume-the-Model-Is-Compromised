# Part 3: rules the agent can propose

A fact says, "The user prefers short reports." A **rule** says, "Always ask for an order number before discussing a refund."

A rule is different because it asks the agent to **behave in a certain way on future turns**. In this lab, an active rule is included in the context of users across the same organisation.

We call this **procedural memory**. Because it changes the agent's future instructions, it is also a control-plane change.

## How a rule is made

The model has the `propose_rule` tool. It accepts the proposed text only. The service gets the organisation and proposer from the verified user. It hashes the exact text and stores the proposal in `mem.rules`.

```text
Model proposes a rule
         |
         v
      proposed
      /      \
  approved  rejected
     |         |
     v         v
   active    rejected
     |
  later retired
     |
     v
   retired
```

By default, a proposal does **nothing** until it has been approved.

A user with an approver role reviews the exact text and submits its hash with the decision. The approver **cannot be the person who proposed the rule**. The service checks this, and a database trigger checks it again.

The database also limits the allowed changes of state. The rule's text and the identity of its original approver cannot be changed in place. An authorised approver may retire an active rule later, without changing who originally approved it.

## How it reaches the model

Context assembly selects **active rules in the user's organisation**. It puts them before long-term memories and chat history.

That does not give the rule power over the business API. A rule saying a refund is approved cannot bypass the separate refund approval and execution path elsewhere in this lab.

## What challenge 9.7 breaks

When `rules.self_activate` is enabled, a model proposal becomes `active` immediately. If the model proposed that text after reading a malicious note, that note may become an instruction for future conversations across the organisation.

Turning self-activation off only protects **new** proposals. Rules that were activated while it was on remain active. The Range's restore also retires rules that became active without approval.

**Read the code:** `rules.py`, `database/memory/migrations/0004_rules.sql` and `0008_rule_retirement.sql`.
