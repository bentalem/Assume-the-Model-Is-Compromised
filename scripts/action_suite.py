"""TS-8 — action and approval suite.

The most important suite in the project. Everything else protects data; this protects money.

Each case establishes one property of the propose → approve → execute chain, against the running
system. Several deliberately corrupt state through a direct database connection to simulate what a
compromised component or an operator mistake would do — the point is that the worker refuses anyway,
because it re-verifies rather than trusting what it is handed.

Run: python scripts/action_suite.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KEYCLOAK = "http://localhost:8080"
REALM = "supportpilot"
CEDAR = "11111111-1111-1111-1111-111111111111"
ALICE = "a1111111-1111-1111-1111-111111111111"
FIONA = "f1111111-1111-1111-1111-111111111111"

GREEN, RED, GREY, YELLOW, RESET = "\033[32m", "\033[31m", "\033[90m", "\033[33m", "\033[0m"

results: list[tuple[str, str, str]] = []


class Failed(Exception):
    pass


_PROBE = """
import json, os, httpx
kw = {}
if os.environ.get("PROBE_BODY"):
    kw["json"] = json.loads(os.environ["PROBE_BODY"])
try:
    r = httpx.request(
        os.environ.get("PROBE_METHOD", "GET"),
        "http://api:8000" + os.environ["PROBE_PATH"],
        headers=json.loads(os.environ.get("PROBE_HEADERS", "{}")),
        timeout=25, **kw,
    )
    print(json.dumps({"status": r.status_code, "body": r.text}))
except Exception as exc:
    print(json.dumps({"status": 0, "body": repr(exc)}))
"""


def api(path, token=None, method="GET", body=None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    env = [
        "-e", f"PROBE_PATH={path}",
        "-e", f"PROBE_METHOD={method}",
        "-e", f"PROBE_HEADERS={json.dumps(headers)}",
    ]
    if body is not None:
        env += ["-e", f"PROBE_BODY={json.dumps(body)}"]
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", *env, "approval-portal", "python", "-c", _PROBE],
        cwd=REPO, capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace",
    )
    line = next((l for l in proc.stdout.splitlines() if l.startswith("{")), None)
    if not line:
        raise Failed(f"probe failed: {(proc.stderr or proc.stdout)[:200]}")
    return json.loads(line)


def sql(statement: str, role: str = "supportpilot_admin") -> str:
    secret = {
        "sp_api_role": "api_db_password",
        "sp_worker_role": "worker_db_password",
    }.get(role, "postgres_bootstrap_password")
    password = (REPO / ".secrets" / secret).read_text(encoding="utf-8").strip()
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "-e", f"PGPASSWORD={password}", "postgres",
         "psql", "-U", role, "-d", "supportpilot", "-tAX", "-c", statement],
        cwd=REPO, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise Failed((proc.stderr or proc.stdout).strip().splitlines()[0][:220])
    return proc.stdout.strip()


def sql_fails(statement: str, role: str) -> str | None:
    try:
        sql(statement, role)
        return None
    except Failed as exc:
        return str(exc)


def token_for(username: str) -> str:
    data = urllib.parse.urlencode({
        "grant_type": "password", "client_id": "supportpilot-test-harness",
        "username": username, "password": f"{username}-local-password", "scope": "openid",
    }).encode()
    url = f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token"
    with urllib.request.urlopen(url, data=data, timeout=20) as response:
        return json.load(response)["access_token"]


def check(case_id: str, description: str):
    def decorator(fn):
        try:
            detail = fn() or ""
            results.append((case_id, "PASS", detail))
            print(f"  {case_id:<8} {GREEN}PASS{RESET}  {description}")
            if detail:
                print(f"           {GREY}{detail}{RESET}")
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            results.append((case_id, "FAIL", message))
            print(f"  {case_id:<8} {RED}FAIL{RESET}  {description}")
            print(f"           {RED}{message}{RESET}")
        return fn
    return decorator


def propose(token, amount="19.90", order="ORD-2001", currency="USD") -> str:
    response = api("/v1/actions/refunds", token, "POST", {
        "order_number": order, "amount": amount, "currency": currency, "reason": "damaged_on_arrival",
    })
    if response["status"] != 201:
        raise Failed(f"proposal failed: {response['status']} {response['body'][:150]}")
    return json.loads(response["body"])["action_id"]


def approve(token, action_id, hash_value=None) -> dict:
    if hash_value is None:
        view = api(f"/internal/approvals/{action_id}", token)
        if view["status"] != 200:
            raise Failed(f"cannot view action: {view['status']}")
        hash_value = json.loads(view["body"])["payload_hash"]
    return api(f"/internal/approvals/{action_id}", token, "POST",
               {"decision": "approved", "approved_hash": hash_value})


def wait_for_state(action_id: str, wanted: set[str], seconds: int = 45) -> str:
    deadline = time.time() + seconds
    state = "?"
    while time.time() < deadline:
        state = sql(f"SELECT state FROM app.action_requests WHERE id='{action_id}'")
        if state in wanted:
            return state
        time.sleep(2)
    return state


def main() -> int:
    print()
    print("SupportPilot action and approval suite (TS-8)")
    print("-" * 78)

    alice = token_for("alice")
    fiona = token_for("fiona")
    bob = token_for("bob")
    mallory = token_for("mallory")

    # --- TS8-01 ------------------------------------------------------------------------------
    @check("TS8-01", "A valid proposal creates a pending action and moves no money")
    def _():
        action_id = propose(alice)
        state = sql(f"SELECT state FROM app.action_requests WHERE id='{action_id}'")
        if state != "PENDING_APPROVAL":
            raise Failed(f"state is {state}")
        executions = sql(
            "SELECT count(*) FROM app.action_executions e "
            "JOIN app.action_jobs j ON j.id = e.job_id "
            f"WHERE j.action_request_id = '{action_id}'"
        )
        if executions != "0":
            raise Failed(f"{executions} execution row(s) exist before approval")
        jobs = sql(f"SELECT count(*) FROM app.action_jobs WHERE action_request_id='{action_id}'")
        if jobs != "0":
            raise Failed("a job was queued before approval")
        return "PENDING_APPROVAL, no job, no execution"

    # --- TS8-02 ------------------------------------------------------------------------------
    @check("TS8-02", "An action cannot be created directly in an approved or queued state")
    def _():
        for state in ("APPROVED", "QUEUED", "SUCCEEDED"):
            statement = (
                "BEGIN; "
                f"SELECT set_config('app.user_id','{ALICE}',true); "
                f"SELECT set_config('app.organization_id','{CEDAR}',true); "
                "SELECT set_config('app.roles','support_agent',true); "
                "INSERT INTO app.action_requests (organization_id, requester_id, action_type, "
                "resource_type, resource_id, payload, payload_hash, state, expires_at) VALUES "
                f"('{CEDAR}','{ALICE}','refund','order','ORD-2001','{{}}'::jsonb, "
                f"repeat('a',64),'{state}', now() + interval '1 day'); COMMIT;"
            )
            if sql_fails(statement, "sp_api_role") is None:
                raise Failed(f"the API role inserted an action directly in {state}")
        return "APPROVED, QUEUED and SUCCEEDED all refused at insert"

    # --- TS8-03 ------------------------------------------------------------------------------
    @check("TS8-03", "The requester cannot approve their own action")
    def _():
        action_id = propose(alice)
        # Through the API, where policy refuses it.
        response = approve(alice, action_id, "0" * 64)
        if response["status"] in (200, 201):
            raise Failed("the API accepted a self-approval")

        # And directly in the database, where the trigger refuses it.
        statement = (
            "BEGIN; "
            f"SELECT set_config('app.user_id','{ALICE}',true); "
            f"SELECT set_config('app.organization_id','{CEDAR}',true); "
            "SELECT set_config('app.roles','finance_approver',true); "
            "INSERT INTO app.approval_decisions (action_request_id, approver_id, decision, "
            f"approved_hash, policy_version) VALUES ('{action_id}','{ALICE}','approved', "
            "repeat('a',64),'test'); COMMIT;"
        )
        error = sql_fails(statement, "sp_api_role")
        if error is None:
            raise Failed("the database accepted a self-approval")
        if "separation of duty" not in error:
            raise Failed(f"refused, but not by the separation-of-duty rule: {error[:120]}")
        return "refused by policy at the API and by the trigger at the database"

    # --- TS8-04 ------------------------------------------------------------------------------
    @check("TS8-04", "Only an authorized approver in the same tenant can decide")
    def _():
        action_id = propose(alice)
        for who, token in (("bob (support_manager)", bob), ("mallory (other tenant)", mallory)):
            response = approve(token, action_id, "0" * 64)
            if response["status"] in (200, 201):
                raise Failed(f"{who} approved the action")
        state = sql(f"SELECT state FROM app.action_requests WHERE id='{action_id}'")
        if state != "PENDING_APPROVAL":
            raise Failed(f"state moved to {state}")
        return "support_manager and a foreign-tenant agent both refused"

    # --- TS8-05 ------------------------------------------------------------------------------
    @check("TS8-05", "An expired action can be neither viewed for approval nor approved")
    def _():
        action_id = propose(alice)

        # Capture the hash while the action is still live. This is the realistic attack: an
        # approver loads the screen, walks away, and submits after the window closes.
        view = api(f"/internal/approvals/{action_id}", fiona)
        if view["status"] != 200:
            raise Failed(f"setup: could not view a live action ({view['status']})")
        hash_value = json.loads(view["body"])["payload_hash"]

        sql(f"UPDATE app.action_requests SET expires_at = now() - interval '1 hour' WHERE id='{action_id}'")

        # The review screen closes too, so an expired action cannot even be re-opened.
        stale_view = api(f"/internal/approvals/{action_id}", fiona)
        if stale_view["status"] == 200:
            raise Failed("an expired action was still viewable for approval")

        # And the decision submitted from the stale screen is refused.
        response = api(f"/internal/approvals/{action_id}", fiona, "POST",
                       {"decision": "approved", "approved_hash": hash_value})
        if response["status"] in (200, 201):
            raise Failed("an expired action was approved from a stale screen")

        decisions = sql(f"SELECT count(*) FROM app.approval_decisions WHERE action_request_id='{action_id}'")
        if decisions != "0":
            raise Failed("a decision row was written for an expired action")
        state = sql(f"SELECT state FROM app.action_requests WHERE id='{action_id}'")
        if state != "PENDING_APPROVAL":
            raise Failed(f"the expired action moved to {state}")
        return f"view {stale_view['status']}, decision {response['status']}, no decision recorded"

    # --- TS8-06 — the integrity check ---------------------------------------------------------
    @check("TS8-06", "Changing the payload after approval stops execution (hash mismatch)")
    def _():
        action_id = propose(alice, amount="19.90")
        response = approve(fiona, action_id)
        if response["status"] != 201:
            raise Failed(f"approval failed: {response['status']} {response['body'][:120]}")

        # Simulate a compromise between approval and execution: raise the amount, leaving the
        # approved hash in place. The worker must notice.
        sql(
            "UPDATE app.action_requests "
            "SET payload = jsonb_set(payload, '{amount}', '\"499.00\"') "
            f"WHERE id='{action_id}'"
        )

        state = wait_for_state(action_id, {"SUCCEEDED", "FAILED"}, seconds=45)
        if state == "SUCCEEDED":
            raise Failed("a tampered payload was executed")

        error = sql(
            "SELECT coalesce(last_error,'') FROM app.action_jobs "
            f"WHERE action_request_id='{action_id}'"
        )
        if "payload_hash_mismatch" not in error:
            raise Failed(f"refused, but not for a hash mismatch: {error[:120]}")
        executions = sql(
            "SELECT count(*) FROM app.action_executions e JOIN app.action_jobs j ON j.id=e.job_id "
            f"WHERE j.action_request_id='{action_id}' AND e.outcome='succeeded'"
        )
        if executions != "0":
            raise Failed("a provider effect was recorded for a tampered payload")
        return f"worker refused with {error}; no provider effect"

    # --- TS8-08 ------------------------------------------------------------------------------
    @check("TS8-08", "Two concurrent claims never take the same job")
    def _():
        # The worker is paused for this case. Otherwise it races the probe for the same queue and
        # the test can pass while proving nothing — which it did on the first run.
        subprocess.run(["docker", "compose", "stop", "worker"], cwd=REPO,
                       capture_output=True, timeout=90)
        try:
            ids = [propose(alice) for _ in range(2)]
            for action_id in ids:
                response = approve(fiona, action_id)
                if response["status"] != 201:
                    raise Failed("setup approval failed")

            queued = sql(
                "SELECT count(*) FROM app.action_jobs WHERE state='QUEUED' AND available_at <= now()"
            )
            if int(queued) < 2:
                raise Failed(f"expected at least 2 queued jobs, found {queued}")

            claim = (
                "UPDATE app.action_jobs SET state='EXECUTING', lease_owner='probe', "
                "lease_expires_at = now() + interval '5 minutes', attempts = attempts + 1 "
                "WHERE id = (SELECT j.id FROM app.action_jobs j "
                "WHERE j.state='QUEUED' AND j.available_at <= now() AND j.attempts < j.max_attempts "
                "ORDER BY j.available_at FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING id::text"
            )
            first = sql(claim)
            second = sql(claim)
            # psql prints "UPDATE 0" when a claim matched nothing.
            claimed = [c for c in (first, second) if c and not c.startswith("UPDATE ")]
            if len(claimed) == 2 and claimed[0] == claimed[1]:
                raise Failed(f"the same job was claimed twice: {claimed[0]}")
            if len(claimed) != 2:
                raise Failed(f"only {len(claimed)} of 2 available jobs were claimed")
            return f"two claims took two different jobs ({claimed[0][:8]}, {claimed[1][:8]})"
        finally:
            # Release the probe's jobs and let the worker resume, whatever happened above.
            sql("UPDATE app.action_jobs SET state='QUEUED', lease_owner=NULL, "
                "lease_expires_at=NULL, attempts = greatest(attempts - 1, 0) "
                "WHERE lease_owner='probe'")
            subprocess.run(["docker", "compose", "start", "worker"], cwd=REPO,
                           capture_output=True, timeout=90)

    # --- TS8-09 ------------------------------------------------------------------------------
    @check("TS8-09", "One idempotency key can carry only one execution")
    def _():
        existing = sql(
            "SELECT idempotency_key FROM app.action_executions ORDER BY started_at DESC LIMIT 1"
        )
        if not existing:
            raise Failed("no execution exists yet to test against")
        error = sql_fails(
            "INSERT INTO app.action_executions (job_id, idempotency_key, provider, outcome) "
            "SELECT job_id, idempotency_key, 'fake', 'succeeded' FROM app.action_executions "
            f"WHERE idempotency_key = '{existing}'",
            "supportpilot_admin",
        )
        if error is None:
            raise Failed("a duplicate idempotency key was accepted")
        if "one_effect_per_key" not in error and "duplicate key" not in error:
            raise Failed(f"rejected for the wrong reason: {error[:120]}")
        return "the unique constraint refused a second execution for the same key"

    # --- TS8-11 ------------------------------------------------------------------------------
    @check("TS8-11", "A crashed worker's job is reclaimed, not stuck in EXECUTING")
    def _():
        action_id = propose(alice)
        if approve(fiona, action_id)["status"] != 201:
            raise Failed("setup approval failed")
        time.sleep(1)

        # Simulate a worker that died mid-execution: EXECUTING with an expired lease.
        sql(
            "UPDATE app.action_jobs SET state='EXECUTING', lease_owner='dead-worker', "
            "lease_expires_at = now() - interval '10 minutes' "
            f"WHERE action_request_id='{action_id}'"
        )
        state = wait_for_state(action_id, {"SUCCEEDED", "FAILED"}, seconds=45)
        if state not in ("SUCCEEDED", "FAILED"):
            raise Failed(f"job stayed stuck: action state is {state}")

        stuck = sql(
            "SELECT count(*) FROM app.action_jobs "
            "WHERE state='EXECUTING' AND lease_expires_at < now() - interval '30 minutes'"
        )
        if stuck != "0":
            raise Failed(f"{stuck} job(s) permanently stuck in EXECUTING")
        return f"expired lease reclaimed; action reached {state}"

    # --- TS8-12 ------------------------------------------------------------------------------
    @check("TS8-12", "A rejected action is never executed")
    def _():
        action_id = propose(alice)
        view = api(f"/internal/approvals/{action_id}", fiona)
        hash_value = json.loads(view["body"])["payload_hash"]
        response = api(f"/internal/approvals/{action_id}", fiona, "POST",
                       {"decision": "rejected", "approved_hash": hash_value})
        if response["status"] != 201:
            raise Failed(f"rejection failed: {response['status']}")

        time.sleep(6)
        state = sql(f"SELECT state FROM app.action_requests WHERE id='{action_id}'")
        if state != "REJECTED":
            raise Failed(f"state is {state}, expected REJECTED")
        jobs = sql(f"SELECT count(*) FROM app.action_jobs WHERE action_request_id='{action_id}'")
        if jobs != "0":
            raise Failed("a rejected action was queued")
        return "REJECTED, never queued, never executed"

    # --- TS8-13 ------------------------------------------------------------------------------
    @check("TS8-13", "A completed refund can be reconstructed from the audit trail alone")
    def _():
        action_id = propose(alice)
        if approve(fiona, action_id)["status"] != 201:
            raise Failed("setup approval failed")
        state = wait_for_state(action_id, {"SUCCEEDED", "FAILED"}, seconds=45)
        if state != "SUCCEEDED":
            raise Failed(f"the action did not succeed: {state}")

        rows = sql(
            "SELECT string_agg(action || '/' || decision || '/' || actor_type, ' | ' "
            "ORDER BY occurred_at) FROM app.audit_events "
            f"WHERE resource_id = '{action_id}' OR result_reference = '{action_id}'"
        )
        for required in ("refund.propose", "refund.approve", "refund.execute"):
            if required not in rows:
                raise Failed(f"the trail is missing {required}: {rows[:160]}")

        # Requester, approver, executor, payload hash, and provider reference must all be present.
        detail = sql(
            "SELECT (SELECT count(*) FROM app.audit_events WHERE action='refund.propose' "
            f"  AND result_reference='{action_id}' AND payload_hash IS NOT NULL)::text || '/' || "
            "(SELECT count(*) FROM app.audit_events WHERE action='refund.approve' "
            f"  AND resource_id='{action_id}' AND payload_hash IS NOT NULL)::text || '/' || "
            "(SELECT count(*) FROM app.audit_events WHERE action='refund.execute' "
            f"  AND resource_id='{action_id}' AND actor_type='workload' AND result_reference IS NOT NULL)::text"
        )
        propose_n, approve_n, execute_n = (int(x) for x in detail.split("/"))
        if not (propose_n and approve_n and execute_n):
            raise Failed(f"incomplete evidence: propose={propose_n} approve={approve_n} execute={execute_n}")
        return "propose, approve and execute events all present with hash and provider reference"

    # --- TS8-14 ------------------------------------------------------------------------------
    @check("TS8-14", "A terminal action cannot be revived; correction needs a new action")
    def _():
        action_id = sql("SELECT id FROM app.action_requests WHERE state='SUCCEEDED' "
                        "ORDER BY updated_at DESC LIMIT 1")
        if not action_id:
            raise Failed("no succeeded action to test against")
        statement = (
            "BEGIN; "
            f"SELECT set_config('app.user_id','{FIONA}',true); "
            f"SELECT set_config('app.organization_id','{CEDAR}',true); "
            "SELECT set_config('app.roles','finance_approver',true); "
            f"UPDATE app.action_requests SET state='PENDING_APPROVAL' WHERE id='{action_id}'; "
            "COMMIT;"
        )
        sql(statement, "sp_api_role")  # the UPDATE itself may report 0 rows rather than error
        state = sql(f"SELECT state FROM app.action_requests WHERE id='{action_id}'")
        if state != "SUCCEEDED":
            raise Failed(f"a completed action was moved back to {state}")
        return "the API role cannot move a SUCCEEDED action back into review"

    # --- worker isolation --------------------------------------------------------------------
    @check("TS8-15", "The worker still cannot read business data")
    def _():
        for table in ("app.customers", "app.orders", "app.tickets", "app.internal_notes"):
            if sql_fails(f"SELECT 1 FROM {table} LIMIT 1", "sp_worker_role") is None:
                raise Failed(f"the worker role read {table}")
        return "customers, orders, tickets and notes all refused for the worker"

    # -----------------------------------------------------------------------------------------
    print("-" * 78)
    passed = sum(1 for _, r, _ in results if r == "PASS")
    failed = sum(1 for _, r, _ in results if r == "FAIL")
    if failed == 0:
        print(f"  {GREEN}ALL CASES PASSED  ({passed}/{passed + failed}){RESET}")
    else:
        print(f"  {RED}{passed} PASSED, {failed} FAILED{RESET}")
        print(f"  {YELLOW}A failure here is a phase-4 blocker.{RESET}")
    print()

    evidence = REPO / "evidence"
    evidence.mkdir(exist_ok=True)
    report = evidence / f"action-suite-{time.strftime('%Y%m%dT%H%M%S')}.json"
    report.write_text(json.dumps({
        "suite": "TS-8",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "passed": passed, "failed": failed,
        "cases": [{"id": i, "result": r, "detail": d} for i, r, d in results],
    }, indent=2), encoding="utf-8")
    print(f"  evidence written to {report.relative_to(REPO)}")
    print()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
