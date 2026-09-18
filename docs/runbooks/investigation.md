# Investigating what happened

You changed something, or the agent did something surprising, and now you want to know what actually
occurred. This is the part of the lab that teaches the most, because the honest answer is almost
never the one you expect.

The governing question, every time:

> **Was a boundary crossed, or did the model merely say something wrong?**

Those are completely different events, and only the evidence tells them apart. A model that says it
was denied when the audit trail says `allowed` is not a control working — it is a control that never
acted, described by something that cannot be trusted to describe it.

---

## Always start here: capture before you change anything

The audit trail is append-only and no runtime role can amend it, but containers restart and logs
roll. Capture first, investigate second.

```bash
mkdir -p findings/$(date +%Y%m%dT%H%M%S) && cd "$_"

docker compose logs --no-color --since 2h > services.log

docker compose exec -T -e PGPASSWORD="$(cat ../../.secrets/auditor_db_password)" postgres \
  psql -U sp_auditor_role -d supportpilot -c "\copy (
    SELECT * FROM app.audit_events WHERE occurred_at > now() - interval '2 hours'
    ORDER BY occurred_at) TO STDOUT WITH CSV HEADER" > audit_events.csv
```

Note the role: `sp_auditor_role` can read the audit trail and write nothing, anywhere. That is the
only role in the system that can read it at all — the API can insert and never read back.

---

## Case 1 · Data crossed a tenant boundary

You suspect a Cedar session saw Northwind data, or the reverse.

### What was allowed

```sql
SELECT occurred_at, actor_id, organization_id, action, resource_type, resource_id, reason
FROM app.audit_events
WHERE decision = 'allowed' AND occurred_at BETWEEN '<from>' AND '<to>'
ORDER BY occurred_at;
```

Answer one narrow question: **which records were returned, to whom.** A tool result that reached the
model may have reached the screen, and anything the agent wrote into a note is now content another
session will read as trusted internal data.

### Which of the two layers failed

There are two, and they fail differently.

| Layer | How you tell | What it means |
|---|---|---|
| Policy | `decision='allowed'` with an unexpected `reason` and `policy_version` | A policy regression. Compare the bundle against `policy/supportpilot/authz.rego` in git. |
| Row-level security | `python scripts/verify_local.py` — watch `V-03`, `V-04`, `V-16` | A grants or RLS regression. Check table ownership and `BYPASSRLS` first. |

If **both** layers allowed it, the bug is neither: the request ran under the wrong
`app.organization_id`. Look for a code path that sets request context from something other than a
verified resource lookup.

There is a fourth possibility worth naming, because it is the one people miss: the read was never
cross-tenant at all, and the *model* described a Cedar record using a name it invented. Check the
`resource_id` in the audit row against what appeared on screen before you conclude anything.

### Reason codes, and why the absent ones matter

```
action          | decision | reason                             | policy_version
----------------+----------+------------------------------------+---------------
customer.search | allowed  | same_organization_and_allowed_role  | 2026-09-07.1
order.read      | denied   | resource_not_visible                | (none)
```

The denial carries **no policy version, and that is the information.** It was refused by the resource
lookup before policy was ever asked — the caller could not see that the record existed, so there was
nothing to have an opinion about. A denial from policy would read
`not_a_member_of_resource_organization` and carry a version.

From outside, both are an identical `404`. Inside, they are different systems, and only the reason
code tells you which one you are looking at. This is what "interpretable" means in an audit trail.

---

## Case 2 · The agent did something after reading untrusted content

A ticket, a customer name, or a tool result appears to have steered the agent.

### Stop the worker first

```bash
docker compose stop worker
```

Nothing approved executes while you look. Leave the read tools running — turning off reads blinds the
investigation.

### Read the session in order

```sql
SELECT occurred_at, action, decision, reason, resource_id, policy_version
FROM app.audit_events WHERE request_id = '<request_id>' ORDER BY occurred_at;
```

Three outcomes, and they are not equally interesting:

- **Every sensitive call shows `denied`.** The boundaries held. The model was manipulated and the
  system refused — that is the system working, not a finding. Add the content to the corpus and move
  on.
- **A sensitive call shows `allowed` that should not have.** A boundary failed. Go to Case 1 and find
  out which layer.
- **An action reached `SUCCEEDED` with no matching `refund.approve` event.** The approval chain
  failed. This is the serious one, and in a real system it is the page-someone-at-night case.

### Then put it back

```sql
UPDATE app.action_jobs SET state='FAILED', last_error='cancelled during investigation'
WHERE state IN ('QUEUED','EXECUTING');
```

Add the exact content that triggered it to
`database/seeds/0002_tickets_and_injection_corpus.sql`, add a case to `scripts/abuse_suite.py`, and
re-run the suite. A finding you cannot reproduce on demand is a story, not a finding.

---

## Case 3 · A credential ended up somewhere it should not

A password in a log line, a token in model context, a secret in a commit.

### Rotate first, investigate second

Every service holds its own credential precisely so that one can be rotated without touching the
others.

```bash
# The API's database credential, as an example.
python - <<'PY'
import secrets, base64, pathlib
pathlib.Path('.secrets/api_db_password').write_text(
    base64.urlsafe_b64encode(secrets.token_bytes(24)).decode().rstrip('='))
PY
docker compose up -d --force-recreate api
```

Then change it in the database as `sp_migrator_role` and confirm the API still starts.

### Find out how far it went

```bash
python scripts/scan_secrets.py --all      # every tracked file
git log -S '<the value>' --all            # did it ever enter history?
docker compose logs --no-color | grep -c '<the value>'
```

The last one should be zero. The API installs a redaction filter on the **root** logger, keyed on
patterns rather than field names, so `password=`, a DSN with credentials, a bearer token and a raw
JWT are all caught wherever they appear — including inside tracebacks from libraries that know
nothing about it.

A secret that reached the model's context is the worst case, because nothing will tell you it
happened. That is the argument for never putting one there.

---

## Afterwards

Four questions, every time. They are worth more than the fix.

1. **Which control actually acted?** Name it. "The system refused" is not an answer.
2. **Was it prevented, or did it merely fail?** A malformed request that never reached the
   authorization pipeline is not proof that authorization worked. This distinction has produced more
   false findings in this lab than anything else.
3. **What would have caught it?** Write that test. If the name of an existing test is a larger claim
   than its assertion, change one of them — a test called "bulk extraction is impossible" that only
   proves a single page was capped is worse than no test, because it stops anyone from looking.
4. **Did your instruments tell the truth?** A test that races a background worker will accuse a
   control that held. A script that prints its expected conclusion is not measuring anything.

> **Your instruments lie before the system does. A false finding destroys trust faster than a missed
> one.**
