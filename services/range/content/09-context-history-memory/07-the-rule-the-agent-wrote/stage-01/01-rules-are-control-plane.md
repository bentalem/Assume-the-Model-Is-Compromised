# A rule is not an ordinary remembered fact

A long-term memory may say the user prefers short reports. A rule tells the agent what to do on **future turns**. In this lab, an active rule applies to the whole organisation.

The model can call `propose_rule`. It cannot approve its own proposal. A person with an approver role must approve the **exact text** and must not be the person who proposed it.

PostgreSQL stores the rule's state and a hash of its text. A database trigger enforces the allowed state changes and prevents self-approval.

## Your task

First propose a rule with the normal approval process. See that it stays `proposed` and does not enter context. Then enable self-activation and submit a proposal again.

Look at its state and at the next context. An instruction taken from one untrusted ticket may now affect future users in the same organisation.

Turning self-activation off prevents new cases. The Range must also retire rules that became active without approval while the setting was on.

An approved instruction in context still cannot bypass the business API's separate permissions and refund approval process.
