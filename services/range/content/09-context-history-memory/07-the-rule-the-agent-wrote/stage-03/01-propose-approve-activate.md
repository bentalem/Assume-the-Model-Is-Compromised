# Propose, approve, activate

The decision chain for a rule:

1. **Propose** — `propose_rule`, the model's tool. The body has one field, `text`. The channel is fixed to `agent` by the route, and the payload hash of the text is stored with it.
2. **State at birth** — `proposed`, unless `rules.self_activate` is on. The insert policy checks the same setting, so the service alone cannot make a rule active.
3. **Decide** — a runtime route, approvers only. The approver sends the hash of the text they read; a different text is a conflict. The trigger refuses a decision by the proposer, even when the proposer is an approver, and the refusal is audited — through a savepoint, so that the attempt most worth recording is not rolled back with the transaction it failed in.
4. **Retire** — also approvers only. Who approved the rule stays on it.

## Two policies, one trigger

With both a "decide" and a "retire" UPDATE policy, PostgreSQL combines them with OR — separately for
the rows an update may touch and for the values it may write. An approver could take an active rule
(retire's rows) and write it back as active with themselves as the approver (decide's values):
forging who approved it. Policies describe rows. They cannot describe transitions. So the trigger
holds the complete table — proposed to decided by someone else, active to retired with the approver
unchanged, nothing out of rejected or retired — and the smoke test proves it as the superuser, whom
no policy restrains.

## What the restore does

Turning self-activation off stops new proposals being born active. The ones already active stay
active, and would be obeyed indefinitely. The Range's restore therefore retires every rule that is
active with nobody recorded as approving it — and only those; a rule a person approved is that
person's decision, and the store's own policy stops the Range from touching it.
