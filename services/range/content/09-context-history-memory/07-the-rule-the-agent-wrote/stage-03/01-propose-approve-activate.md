# Propose, approve, activate, retire

The model's `propose_rule` tool sends only text. The service records the proposer and hashes the exact content. Normally the new rule starts as `proposed`.

An authorised person uses a separate runtime route to approve or reject it. The decision must name the hash of the text they read. The approver cannot be the proposer. The database trigger checks the same rule and allows only legal state changes.

Only `active` rules enter context. A later approver can retire an active rule without changing the original approval.

When `rules.self_activate` is on, a model proposal is born active and skips the decision path. Turning the setting off does not retire rules already activated that way. The Range's restore does both.

## Take it to a review

- Can any model-facing tool approve a rule or choose its own state?
- Is an approval tied to the exact text, not only a record ID?
- Does the database enforce separation of duties if a new API path is added?
- How are rules activated without approval found and retired?
