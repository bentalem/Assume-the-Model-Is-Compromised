# Runbook — reconciling an ambiguous or failed action

> Task `P4-21`. Use when a refund's outcome is unclear: the worker reported `ambiguous`, a job
> exhausted its attempts, or a restore reintroduced approved work.

**The rule that governs everything below:** never re-issue a refund to "make sure it went through".
Ask the provider what happened first. An ambiguous result means the effect *may* have landed, and a
blind retry is how one refund becomes two.

## 1. Establish what the system believes

```bash
# Replace <action_id>. Run as the auditor role; this is a read.
docker compose exec -T -e PGPASSWORD="$(cat .secrets/auditor_db_password)" postgres \
  psql -U sp_auditor_role -d supportpilot -c "
    SELECT r.state AS action_state, r.payload_hash,
           d.decision, d.approver_id, d.decided_at,
           j.state AS job_state, j.attempts, j.last_error,
           e.idempotency_key, e.outcome, e.provider_reference, e.finished_at
    FROM app.action_requests r
    LEFT JOIN app.approval_decisions d ON d.action_request_id = r.id
    LEFT JOIN app.action_jobs j        ON j.action_request_id = r.id
    LEFT JOIN app.action_executions e  ON e.job_id = j.id
    WHERE r.id = '<action_id>';"
```

Read the result as follows.

| What you see | What it means |
|---|---|
| `outcome = succeeded` with a `provider_reference` | Done. Nothing to reconcile. |
| `outcome = ambiguous`, no reference | The provider was asked and did not answer clearly. Go to step 2. |
| An execution row exists but `finished_at` is null | A worker died between reserving the key and recording the result. Go to step 2. |
| No execution row, `job_state = FAILED` | The worker refused before calling the provider. Read `last_error`; go to step 4. |
| `action_state = CANCELLED`, `last_error` mentions a restore | Restored backlog. Go to step 3. |

## 2. Ask the provider, using the idempotency key

The key is the join between our records and theirs. It is `<action_id>:<first 32 chars of the
payload hash>` and appears in `action_executions.idempotency_key`.

```bash
# Local: the fake adapter answers from its own store.
docker compose exec -T worker python -c "
from supportpilot_worker.adapters.refund import FakeRefundAdapter
print(FakeRefundAdapter().lookup(idempotency_key='<key>'))"
```

With a real provider (once OD-02 is decided), query their API by idempotency key — never by
customer or amount, which can match a different refund.

- **The provider has a record and it succeeded.** The effect landed. Record it and stop:

  ```sql
  UPDATE app.action_executions
  SET outcome = 'succeeded', provider_reference = '<their reference>',
      detail = 'reconciled manually: provider confirmed', finished_at = now()
  WHERE idempotency_key = '<key>';

  UPDATE app.action_jobs        SET state = 'SUCCEEDED' WHERE id = '<job_id>';
  UPDATE app.action_requests    SET state = 'SUCCEEDED', updated_at = now() WHERE id = '<action_id>';
  ```

- **The provider has no record.** The effect did not land. The job may retry, which happens on its
  own once the backoff elapses. Do nothing further.

- **The provider is unreachable.** Stop. Do not guess. Leave the action as it is — an action stuck
  in an ambiguous state is safe; a duplicated refund is not — and escalate to the action owner.

Every manual `UPDATE` above must be accompanied by an audit event, because the trail is what the
next person reads:

```sql
INSERT INTO app.audit_events (
    request_id, actor_type, actor_id, organization_id, action,
    resource_type, resource_id, decision, reason, payload_hash, result_reference
) VALUES (
    'manual-reconcile-<ticket>', 'user', '<your user id>', '<organization_id>', 'refund.reconcile',
    'action_request', '<action_id>', 'succeeded', 'manual reconciliation after ambiguous outcome',
    '<payload_hash>', '<provider reference>'
);
```

## 3. Restored backlog after a database restore

`backup_restore_drill.py` cancels queued and executing jobs on restore rather than resuming them,
because a restored approval has usually already been honoured and the restore predates the execution
row that would have stopped a retry.

For each cancelled action, work through step 2. If the provider confirms the refund happened, close
the action as `SUCCEEDED` with the provider's reference. If it did not, the requester raises a **new**
action — see step 5.

## 4. The worker refused before calling the provider

`last_error` names the check that failed. These are not reconciliation problems; they are signals.

| `last_error` | Meaning | Action |
|---|---|---|
| `payload_hash_mismatch_stored` | The stored payload no longer matches its own hash | **Treat as an incident.** Something modified an approved action. Follow the injection-driven-action runbook and preserve evidence. |
| `payload_hash_mismatch_approved` | The approval was for a different payload | Same as above. |
| `self_approval_detected` | Requester and approver are the same | Policy and the trigger both failed. Incident; do not "fix" the data. |
| `approval_expired` | The window closed before execution | Normal. The requester raises a new action. |
| `no_approval_decision` / `action_was_rejected` | Correct refusal | Normal. Nothing to do. |

## 5. Corrections are new actions, never edits

If a refund needs to be issued, re-issued, or reversed, the requester raises a **new** action that
goes through approval like any other. Do not move a terminal action back into review, and do not
adjust an amount in place — SP-OPS-001 §6 requires it, and the state machine and row policies both
refuse it anyway (`TS8-14`).

## 6. Before closing

- [ ] The provider's own record agrees with `action_executions`.
- [ ] An audit event exists for every manual change, naming who made it and why.
- [ ] If the cause was a refused check in step 4, an incident record exists and a regression test
      has been added.
- [ ] If the cause was a provider behaviour we did not expect, the adapter's contract tests have a
      new case.
