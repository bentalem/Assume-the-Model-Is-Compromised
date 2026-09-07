# Runbooks — security incidents

> Task `P5-09`. Three procedures from SP-OPS-001 §8. Each is written to be followed under pressure
> by someone who did not build the system.

**Before anything else, in all three cases: preserve evidence before you change state.** The audit
trail is append-only and no runtime role can amend it, but containers can be restarted and logs can
roll. Capture first, then contain.

```bash
# Snapshot the evidence for a time window. Do this first, every time.
mkdir -p evidence/incident-$(date +%Y%m%dT%H%M%S) && cd "$_"
docker compose logs --no-color --since 2h > services.log
docker compose exec -T -e PGPASSWORD="$(cat ../../.secrets/auditor_db_password)" postgres \
  psql -U sp_auditor_role -d supportpilot -c "\copy (
    SELECT * FROM app.audit_events WHERE occurred_at > now() - interval '2 hours'
    ORDER BY occurred_at) TO STDOUT WITH CSV HEADER" > audit_events.csv
```

---

## 1. Suspected cross-tenant exposure

Someone may have seen another organization's data.

### Contain

1. **Disable the affected tool**, not the whole service, if the exposure is limited to one
   operation. Remove it from the OpenAPI action document and redeploy, so the model can no longer
   call it:
   ```bash
   # Edit APPROVED_OPERATIONS in scripts/export_openapi.py, then:
   python scripts/export_openapi.py && docker compose up -d --build api
   ```
2. If the exposure is broad or the boundary is unclear, stop the API. A stopped API denies
   everything, which is the correct failure direction.

### Establish scope

```sql
-- What was allowed, for whom, on what, in the window.
SELECT occurred_at, actor_id, organization_id, action, resource_type, resource_id, reason
FROM app.audit_events
WHERE decision = 'allowed' AND occurred_at BETWEEN '<from>' AND '<to>'
ORDER BY occurred_at;
```

The question to answer is narrow: **which records were returned, to whom, and did model output
carry them further?** A tool result that reached the model may have reached the user's screen and
their notes.

Then find the layer that failed. There are two, and they fail differently:

| Check | Command | If it fails |
|---|---|---|
| Did policy allow it? | Look for `decision='allowed'` with an unexpected `reason` and `policy_version` | Policy regression. Compare the bundle against the reviewed version. |
| Did the database allow it? | `python scripts/verify_local.py` (V-03, V-04) and the smoke tests | RLS or grant regression. Check table ownership and `BYPASSRLS` immediately. |

If **both** layers allowed it, the exposure is a tenant-context bug in the API — the request ran
under the wrong `app.organization_id`. Search for a code path that sets context from anything other
than a verified resource lookup.

### Recover

1. Correct the policy or the code. Do not widen a test to make it pass.
2. Add a regression case to the suite that should have caught it — `TS-6` for tenancy, `TS-2` for
   policy, `TS-3` for grants.
3. Rotate credentials only if one was exposed; a data exposure does not by itself require it.
4. Follow the approved notification process. That decision is not an engineering one.

---

## 2. Suspected prompt-injection-driven action

Content in a ticket, a customer name, or a document appears to have caused the agent to do
something it should not.

### Contain

```bash
docker compose stop worker      # nothing approved executes while you look
```

Pause the affected action type by removing its operation from the action document, as above. Leave
read tools running unless they are implicated: turning off reads blinds the people investigating.

### Establish what actually happened

The essential question is **whether a trusted boundary was crossed, or whether the model merely
said something wrong**. These are very different incidents, and the audit trail distinguishes them.

```sql
-- Everything in the session, in order.
SELECT occurred_at, action, decision, reason, resource_id, policy_version
FROM app.audit_events WHERE request_id = '<request_id>' ORDER BY occurred_at;
```

- **Every sensitive call shows `decision='denied'`** — the boundaries held. The model was
  manipulated; the system refused. This is a model-behaviour issue: tighten agent instructions,
  add the content to the injection corpus, and move on. Not a breach.
- **A sensitive call shows `decision='allowed'` that should not have been** — a boundary failed.
  Treat as a breach and continue below.
- **An action reached `SUCCEEDED` without a matching `refund.approve` event** — the approval chain
  failed. This is the most serious case. Escalate immediately.

### Recover

1. Cancel unexecuted jobs:
   ```sql
   UPDATE app.action_jobs SET state='FAILED', last_error='cancelled: incident <ref>'
   WHERE state IN ('QUEUED','EXECUTING');
   ```
2. Reconcile anything that may have executed — see [reconciliation.md](reconciliation.md).
3. Add the exact content that triggered it to the corpus in
   `database/seeds/0002_tickets_and_injection_corpus.sql`, and add a case to
   `scripts/abuse_suite.py`.
4. Re-enable the action type only after the new case passes.

---

## 3. Credential exposure

A secret may be in a log, an image, a prompt, a repository, or a screenshot.

### Contain — rotate first, investigate second

Rotation is cheap here; every credential is per-service and independently rotatable, which is why
they were separated in the first place.

```bash
# Example: the API's database credential.
NEW=$(python -c "import base64,secrets;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('='))")
docker compose exec -T -e PGPASSWORD="$(cat .secrets/postgres_bootstrap_password)" postgres \
  psql -U supportpilot_admin -d supportpilot -c "ALTER ROLE sp_api_role PASSWORD '$NEW';"
printf '%s' "$NEW" > .secrets/api_db_password
docker compose up -d --force-recreate api
```

Rotate the model provider key through the provider's console, and the OAuth material through
Keycloak. The realm's signing keys rotate in the Keycloak admin console; the API picks up the new
key set on its next fetch without a restart (`TS1-09` covers this).

### Establish scope

```bash
python scripts/scan_secrets.py --all          # is it in the repository now?
git log -p --all -S '<the secret>' | head     # was it ever committed?
docker compose logs --no-color | python -c "
import sys; from services.api.src.supportpilot_api.observability import redact
print('LEAK' if any(l != redact(l) for l in sys.stdin) else 'clean')"
```

Check every place the baseline lists: source, images, prompts, logs, builds, and the agent
configuration in Onyx.

### Recover

1. Confirm the old credential no longer works.
2. Review what was accessed while it was valid — for a database credential, `audit_events` filtered
   by `actor_type='workload'`.
3. If it was committed, history rewriting is a decision for the repository owner; rotation is not
   optional either way.
4. Add a detection for the shape that escaped: a pattern in `scripts/scan_secrets.py`, or a
   redaction rule in `observability.py`. Every incident should leave the scanner smarter — both of
   the gaps currently covered there were found exactly this way.

---

## After any incident

- [ ] Evidence snapshot stored with the incident reference.
- [ ] A regression test exists that would have caught it.
- [ ] The threat model is updated if a new path was found (`ST-01`).
- [ ] The risk register in [../10-risk-and-decisions.md](../10-risk-and-decisions.md) reflects what
      was learned.
- [ ] Controls are re-enabled only after the new test passes.
