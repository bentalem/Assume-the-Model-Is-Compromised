#!/usr/bin/env python3
"""The memory service, tested against the running stack.

The service's unit tests stub its stores, and say why: row-level security lives in memory-db and
credential scoping lives in Qdrant, and a stub cannot enforce either — a test that faked them would
be testing the fake. This suite is where those properties are actually proven: real tokens, real
requests over the `app` network the way an agent runtime makes them, real stores behind them.

Every capability gets the lab's four cases — positive, negative, cross-tenant, malformed — and the
cross-tenant ones run in both vector layouts, because the shared layout is where a tenant boundary
becomes a filter.

    python scripts/memory_suite.py          requires `docker compose --profile memory up -d`

Settings are flipped the way the Range flips them, through range_mem.set_setting as mem_range_role,
and every one is restored before the suite exits, whatever happens.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import ssl
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KEYCLOAK = "https://localhost:8443"
GREEN, RED, GREY, RESET = "\033[32m", "\033[31m", "\033[90m", "\033[0m"
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    mark = f"{GREEN}ok{RESET}  " if ok else f"{RED}FAIL{RESET}"
    print(f"  {mark} {name}" + (f"  {GREY}{detail}{RESET}" if detail else ""))
    if not ok:
        failures.append(name)
    return ok


def compose(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", *args], cwd=REPO, capture_output=True, text=True,
                          timeout=timeout, encoding="utf-8", errors="replace")


def token(user: str, client: str = "supportpilot-test-harness") -> str:
    context = ssl.create_default_context()
    certificate = REPO / ".secrets" / "tls" / "keycloak.crt"
    if certificate.exists():
        context.load_verify_locations(cafile=str(certificate))
    data = urllib.parse.urlencode({
        "grant_type": "password", "client_id": client, "username": user,
        "password": f"{user}-local-password", "scope": "openid",
    }).encode()
    url = f"{KEYCLOAK}/realms/supportpilot/protocol/openid-connect/token"
    with urllib.request.urlopen(url, data=data, timeout=20, context=context) as response:
        return json.load(response)["access_token"]


_RUNNER = """
import json, sys, httpx
calls = json.loads(sys.stdin.read())
out = []
for c in calls:
    headers = {"Authorization": "Bearer " + c["token"]} if c.get("token") else {}
    try:
        r = httpx.request(c["method"], "http://memory:8000" + c["path"], headers=headers,
                          json=c.get("json"), timeout=60)
        out.append({"status": r.status_code, "body": r.json() if r.content else None})
    except Exception as exc:
        out.append({"status": 0, "body": repr(exc)})
print(json.dumps(out))
"""


def send(*calls: dict) -> list[dict]:
    """Make requests from inside the `app` network, in order, and return status and body for each."""
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "approval-portal", "python", "-c", _RUNNER],
        cwd=REPO, input=json.dumps(list(calls)), capture_output=True, text=True, timeout=300,
        encoding="utf-8", errors="replace",
    )
    line = next((l for l in proc.stdout.splitlines() if l.startswith("[")), None)
    if line is None:
        raise SystemExit(f"requests produced no result: {(proc.stderr or proc.stdout)[:300]}")
    return json.loads(line)


def one(method: str, path: str, tok: str | None, body: dict | None = None) -> dict:
    return send({"method": method, "path": path, "token": tok, "json": body})[0]


def set_setting(key: str, value: str) -> None:
    password = (REPO / ".secrets" / "range_memory_db_password").read_text(encoding="utf-8").strip()
    proc = compose("exec", "-T", "-e", f"PGPASSWORD={password}", "memory-db", "psql", "-h",
                   "localhost", "-U", "mem_range_role", "-d", "memory", "-tAX", "-c",
                   f"SELECT range_mem.set_setting('{key}', '{value}')")
    if proc.returncode != 0:
        raise SystemExit(f"could not set {key}: {proc.stderr.strip()[:200]}")


def mem_sql(sql: str) -> str:
    """Observe memory-db as its bootstrap user, from inside its own container. Observation only:
    every change the suite makes goes through the service, or through the Range's own functions."""
    proc = compose("exec", "-T", "memory-db", "psql", "-U", "memory_admin", "-d", "memory",
                   "-tAX", "-c", sql)
    if proc.returncode != 0:
        raise SystemExit(f"memory-db query failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.strip()


def range_mem(function: str) -> str:
    """Call one of the Range's functions in memory-db, as the Range's role."""
    password = (REPO / ".secrets" / "range_memory_db_password").read_text(encoding="utf-8").strip()
    proc = compose("exec", "-T", "-e", f"PGPASSWORD={password}", "memory-db", "psql", "-h",
                   "localhost", "-U", "mem_range_role", "-d", "memory", "-tAX", "-c",
                   f"SELECT range_mem.{function}()")
    if proc.returncode != 0:
        raise SystemExit(f"range_mem.{function} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.strip()


def core_range(function: str) -> None:
    """Call one of the Range's functions in the core database — how 9.4 demotes bob."""
    password = (REPO / ".secrets" / "range_db_password").read_text(encoding="utf-8").strip()
    proc = compose("exec", "-T", "-e", f"PGPASSWORD={password}", "postgres", "psql", "-h",
                   "localhost", "-U", "sp_range_role", "-d", "supportpilot", "-tAX", "-c",
                   f"SELECT range.{function}()")
    if proc.returncode != 0:
        raise SystemExit(f"range.{function} failed: {proc.stderr.strip()[:200]}")


def subject(tok: str) -> str:
    payload = tok.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["sub"]


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def context(tok: str, query: str = "what should I know", session_id: str | None = None) -> dict:
    body = {"query": query} | ({"session_id": session_id} if session_id else {})
    return one("POST", "/v1/context", tok, body)


def rendered(response: dict) -> str:
    return answered(response, "context").get("rendered", "")


SECURE = {
    "write.secret_filter": "on", "context.provenance": "on", "history.org_readable": "false",
    "history.revalidate": "on", "write.auto_confirm": "false", "store.layout": "per_tenant",
    "rules.self_activate": "false", "forget.scope": "all",
}


def restore_all() -> None:
    for key, value in SECURE.items():
        set_setting(key, value)


def answered(response: dict, what: str) -> dict:
    # Most checks here say something is *absent*, and an error response has nothing in it. So a
    # read that did not succeed is a failure of its own, never a quiet pass for the check above it:
    # something that did not appear because the call broke was not prevented.
    if response.get("status") != 200:
        check(f"{what} answered", False, f"HTTP {response.get('status')}")
    return response.get("body") or {}


def contents(response: dict) -> list[str]:
    return [m["content"] for m in answered(response, "recall").get("results", [])]


def main() -> int:
    print("\nMemory service — against the running stack")
    print("-" * 74)
    if "memory" not in compose("ps", "--format", "{{.Service}}").stdout.split():
        print("  the memory profile is not up: docker compose --profile memory up -d")
        return 2

    restore_all()
    alice, bob, mallory = token("alice"), token("bob"), token("mallory")
    foreign = token("alice", client="another-service")
    marker = "Alice's locker combination is PLUM-7719."
    try:
        # ------------------------------------------------------------------------------------
        print(f"\n  {GREY}identity{RESET}")
        check("no token is refused", one("GET", "/v1/memories/search?q=hello", None)["status"] == 401)
        check("a token without the memory audience is refused",
              one("GET", "/v1/memories/search?q=hello", foreign)["status"] == 401)
        r = one("POST", "/v1/memories", alice, {"content": "x y z", "user_id": "bob"})
        check("a user id in the body is refused, not ignored", r["status"] == 400)
        for field in ("channel", "status", "organization_id", "approved"):
            r = one("POST", "/v1/memories", alice, {"content": "x y z", field: "anything"})
            check(f"`{field}` in the body is refused", r["status"] == 400)

        # ------------------------------------------------------------------------------------
        print(f"\n  {GREY}remember and confirm{RESET}")
        r = one("POST", "/v1/memories", alice, {"content": marker})
        mid = r["body"]["memory_id"]
        check("remember succeeds, and is unconfirmed", r["status"] == 201
              and r["body"]["status"] == "unconfirmed")
        pending = one("GET", "/v1/memories/pending", alice)
        check("it waits on alice's confirmation screen",
              pending["status"] == 200
              and mid in [m["memory_id"] for m in pending["body"]["pending"]])
        check("not on a colleague's",
              mid not in [m["memory_id"] for m in
                          (one("GET", "/v1/memories/pending", bob)["body"] or {}).get("pending", [])])
        check("nor on another tenant's",
              mid not in [m["memory_id"] for m in
                          (one("GET", "/v1/memories/pending", mallory)["body"] or {}).get("pending",
                                                                                         [])])
        check("an unconfirmed memory stays out of recall",
              marker not in contents(one("GET", "/v1/memories/search?q=locker combination", alice)))
        check("the model's route cannot confirm: bob confirming alice's memory is refused",
              one("POST", f"/v1/memories/{mid}/confirm", bob)["status"] == 404)
        check("the user's confirmation, through the runtime, succeeds",
              one("POST", f"/v1/memories/{mid}/confirm", alice)["status"] == 200)
        check("a confirmed memory is recalled",
              marker in contents(one("GET", "/v1/memories/search?q=locker combination", alice)))
        check("a credential is refused at write",
              one("POST", "/v1/memories", alice, {"content": "key AKIAIOSFODNN7EXAMPLE"})["body"]
              == {"error": {"code": "secret_refused", "request_id": "mem-unassigned"}})
        check("a one-character query is malformed",
              one("GET", "/v1/memories/search?q=a", alice)["status"] == 400)

        # ------------------------------------------------------------------------------------
        for layout in ("per_tenant", "shared"):
            print(f"\n  {GREY}cross-user and cross-tenant, {layout} layout{RESET}")
            set_setting("store.layout", layout)
            got_bob = contents(one("GET", "/v1/memories/search?q=locker combination", bob))
            got_mallory = contents(one("GET", "/v1/memories/search?q=locker combination", mallory))
            check(f"{layout}: a colleague does not recall alice's memory", marker not in got_bob)
            check(f"{layout}: another tenant does not recall alice's memory",
                  marker not in got_mallory)
            check(f"{layout}: alice still recalls her own",
                  marker in contents(one("GET", "/v1/memories/search?q=locker combination", alice)))
        set_setting("store.layout", "per_tenant")

        # ------------------------------------------------------------------------------------
        print(f"\n  {GREY}forget{RESET}")
        s = one("POST", f"/v1/memories/{mid}/summaries", alice)
        check("a summary is derived", s["status"] == 201 and s["body"]["derived_from"] == mid)
        check("bob cannot forget alice's memory",
              one("DELETE", f"/v1/memories/{mid}", bob)["status"] == 404)
        check("mallory cannot forget alice's memory",
              one("DELETE", f"/v1/memories/{mid}", mallory)["status"] == 404)
        check("alice forgets it", one("DELETE", f"/v1/memories/{mid}", alice)["status"] == 200)
        after = contents(one("GET", "/v1/memories/search?q=locker combination", alice))
        check("neither the memory nor its summary is recalled afterwards",
              not any("PLUM-7719" in c for c in after), f"{len(after)} result(s)")
        check("forgetting twice is not found",
              one("DELETE", f"/v1/memories/{mid}", alice)["status"] == 404)
        check("a malformed id is refused before the store",
              one("DELETE", "/v1/memories/not-a-uuid", alice)["status"] == 400)

        # ------------------------------------------------------------------------------------
        print(f"\n  {GREY}history{RESET}")
        created = one("POST", "/v1/sessions", alice, {"title": "suite"})
        sid = created["body"]["session_id"]
        one("POST", f"/v1/sessions/{sid}/turns", alice, {"role": "user", "content": "hello there"})
        check("alice reads her own transcript",
              one("GET", f"/v1/sessions/{sid}/turns", alice)["status"] == 200)
        check("bob cannot read it with quality review off",
              one("GET", f"/v1/sessions/{sid}/turns", bob)["status"] == 404)
        set_setting("history.org_readable", "true")
        r = one("GET", f"/v1/sessions/{sid}/turns", bob)
        check("with quality review on, bob (a manager) reads it, marked as such",
              r["status"] == 200 and r["body"]["read_as"] == "organisation")
        check("even so, mallory (another tenant) cannot",
              one("GET", f"/v1/sessions/{sid}/turns", mallory)["status"] == 404)
        check("even so, bob cannot write to it",
              one("POST", f"/v1/sessions/{sid}/turns", bob, {"role": "user", "content": "x"})
              ["status"] == 404)
        set_setting("history.org_readable", "false")
        r = one("POST", f"/v1/sessions/{sid}/turns", alice,
                {"role": "tool", "content": "api key AKIAIOSFODNN7EXAMPLE returned"})
        check("a credential in a tool turn is redacted at write", r["body"].get("redacted") is True)
        transcript = one("GET", f"/v1/sessions/{sid}/turns", alice)["body"]["turns"]
        check("the stored turn does not contain it",
              not any("AKIAIOSFODNN7EXAMPLE" in t["content"] for t in transcript))

        # ------------------------------------------------------------------------------------
        run = secrets.token_hex(3)  # rules are never deleted, so each run's text is its own
        fiona = token("fiona")
        print(f"\n  {GREY}rules{RESET}")
        text = f"Suite rule {run}: greet the customer by name."
        r = one("POST", "/v1/rules/proposals", alice, {"text": text})
        rid = r["body"]["rule_id"]
        check("the agent proposes a rule, and it is only a proposal",
              r["status"] == 201 and r["body"]["state"] == "proposed")
        check("a proposal is not in the proposer's context", text not in rendered(context(alice)))
        check("alice, who is not an approver, cannot decide it",
              one("POST", f"/v1/rules/proposals/{rid}/decision", alice,
                  {"decision": "approve", "payload_hash": sha256(text)})["status"] == 403)
        check("an approval of different text is refused",
              one("POST", f"/v1/rules/proposals/{rid}/decision", bob,
                  {"decision": "approve", "payload_hash": sha256(text + " ")})["status"] == 409)
        check("a decision that is neither approve nor reject is malformed",
              one("POST", f"/v1/rules/proposals/{rid}/decision", bob,
                  {"decision": "maybe", "payload_hash": sha256(text)})["status"] == 400)
        n_text = f"Suite rule {run}: northwind only."
        nid = one("POST", "/v1/rules/proposals", mallory, {"text": n_text})["body"]["rule_id"]
        check("bob, an approver in cedar, cannot see or decide a northwind proposal",
              one("POST", f"/v1/rules/proposals/{nid}/decision", bob,
                  {"decision": "approve", "payload_hash": sha256(n_text)})["status"] == 404)
        queue = one("GET", "/v1/rules/review?state=proposed", fiona)
        queued = {q["rule_id"]: q for q in (queue["body"] or {}).get("rules", [])}
        check("fiona's review queue shows the proposal, with the hash of its text",
              queue["status"] == 200 and queued.get(rid, {}).get("payload_hash") == sha256(text))
        check("and not northwind's", nid not in queued)
        check("alice, not an approver, has no review queue",
              one("GET", "/v1/rules/review?state=proposed", alice)["status"] == 403)
        check("a review of a state that is not reviewable is malformed",
              one("GET", "/v1/rules/review?state=retired", fiona)["status"] == 400)
        r = one("POST", f"/v1/rules/proposals/{rid}/decision", bob,
                {"decision": "approve", "payload_hash": sha256(text)})
        check("bob approves the exact text, and the rule is active",
              r["status"] == 200 and r["body"]["state"] == "active")
        block = rendered(context(alice))
        check("the active rule is in alice's context, with who approved it",
              text in block and f"approved by {subject(bob)}" in block)
        check("it is not in mallory's", text not in rendered(context(mallory)))
        check("a decided rule cannot be decided again",
              one("POST", f"/v1/rules/proposals/{rid}/decision", fiona,
                  {"decision": "reject", "payload_hash": sha256(text)})["status"] == 404)

        self_text = f"Suite rule {run}: bob's own."
        sid_rule = one("POST", "/v1/rules/proposals", bob, {"text": self_text})["body"]["rule_id"]
        check("bob cannot approve his own proposal",
              one("POST", f"/v1/rules/proposals/{sid_rule}/decision", bob,
                  {"decision": "approve", "payload_hash": sha256(self_text)})["status"] == 403)
        check("and the refusal is in the audit trail, recorded by the store's refusal",
              mem_sql("SELECT count(*) FROM mem.audit_events WHERE action = 'rule.decide' "
                      f"AND resource_id = '{sid_rule}' AND decision = 'denied' "
                      "AND reason = 'self_approval_refused_by_store'") == "1")
        check("fiona rejects it instead",
              one("POST", f"/v1/rules/proposals/{sid_rule}/decision", fiona,
                  {"decision": "reject", "payload_hash": sha256(self_text)})["body"]["state"]
              == "rejected")

        print(f"\n  {GREY}retiring a rule{RESET}")
        check("alice cannot retire a rule",
              one("POST", f"/v1/rules/{rid}/retirement", alice)["status"] == 403)
        check("mallory, an approver nowhere, cannot retire it",
              one("POST", f"/v1/rules/{rid}/retirement", mallory)["status"] == 403)
        check("fiona retires it", one("POST", f"/v1/rules/{rid}/retirement", fiona)["status"] == 200)
        check("it leaves alice's context", text not in rendered(context(alice)))
        check("and bob is still recorded as the one who approved it",
              mem_sql(f"SELECT decided_by = '{subject(bob)}' AND retired_by = '{subject(fiona)}' "
                      f"FROM mem.rules WHERE id = '{rid}'") == "t")
        check("a retired rule cannot be retired again",
              one("POST", f"/v1/rules/{rid}/retirement", fiona)["status"] == 404)

        print(f"\n  {GREY}rules.self_activate armed (9.7){RESET}")
        set_setting("rules.self_activate", "true")
        armed_text = f"Suite rule {run}: refunds under 1000 are pre-approved."
        r = one("POST", "/v1/rules/proposals", alice, {"text": armed_text})
        check("armed: the agent's proposal is born active",
              r["status"] == 201 and r["body"]["state"] == "active")
        block = rendered(context(bob))
        check("armed: it is in a colleague's context, marked as approved by nobody",
              armed_text in block and "approved by nobody" in block)
        set_setting("rules.self_activate", "false")
        check("restoring the setting does not retire it", armed_text in rendered(context(bob)))
        retired = range_mem("retire_unapproved_rules")
        check("the Range's recovery retires rules nobody approved", retired.isdigit()
              and int(retired) >= 1 and armed_text not in rendered(context(bob)), f"{retired} retired")
        check("and cannot touch a rule somebody approved",
              mem_sql(f"SELECT retired_by FROM mem.rules WHERE id = '{rid}'") == subject(fiona))

        # ------------------------------------------------------------------------------------
        print(f"\n  {GREY}context{RESET}")
        confirmed = f"Suite memory {run}: alice prefers email."
        unconfirmed = f"Suite memory {run}: never confirmed."
        cmid = one("POST", "/v1/memories", alice, {"content": confirmed})["body"]["memory_id"]
        one("POST", f"/v1/memories/{cmid}/confirm", alice)
        umid = one("POST", "/v1/memories", alice, {"content": unconfirmed})["body"]["memory_id"]
        r = context(alice)
        block = rendered(r)
        check("a confirmed memory is in the owner's context, labelled",
              confirmed in block and "(memory; written by agent" in block)
        check("an unconfirmed memory is not", unconfirmed not in block)
        check("a colleague's context does not contain it", confirmed not in rendered(context(bob)))
        check("another tenant's context does not contain it",
              confirmed not in rendered(context(mallory)))
        cid = r["body"]["context_id"]
        check("the block is logged as delivered, with its audit event",
              mem_sql(f"SELECT (SELECT count(*) FROM mem.context_log WHERE id = '{cid}' "
                      f"AND owner_sub = '{subject(alice)}' AND rendered LIKE '%{run}%')"
                      f" || ':' || (SELECT count(*) FROM mem.audit_events WHERE "
                      f"action = 'context.assemble' AND resource_id = '{cid}')") == "1:1")
        check("an empty query is malformed", context(alice, query="")["status"] == 400)
        check("a session id that is not one is malformed",
              context(alice, session_id="not-a-session")["status"] == 400)
        check("an unknown field is refused",
              one("POST", "/v1/context", alice, {"query": "x", "user_id": "bob"})["status"] == 400)

        set_setting("context.provenance", "off")
        block = rendered(context(alice))
        check("provenance off (9.2): the memory is there, and nothing says where it came from",
              confirmed in block and "(memory;" not in block and "retrieved context" not in block)
        set_setting("context.provenance", "on")

        set_setting("write.auto_confirm", "true")
        auto = f"Suite memory {run}: written by the agent alone."
        r = one("POST", "/v1/memories", alice, {"content": auto})
        amid = r["body"]["memory_id"]
        check("auto_confirm armed (9.5): the agent's write is born confirmed",
              r["body"]["status"] == "confirmed" and auto in rendered(context(alice)))
        set_setting("write.auto_confirm", "false")

        set_setting("write.secret_filter", "off")
        r = one("POST", "/v1/memories", alice, {"content": f"key {run} AKIAIOSFODNN7EXAMPLE"})
        check("secret filter off (9.1): a credential is stored", r["status"] == 201)
        smid = r["body"].get("memory_id")
        set_setting("write.secret_filter", "on")
        for m in (cmid, umid, amid, smid):
            if m:
                one("DELETE", f"/v1/memories/{m}", alice)
        check("the suite's memories are forgotten",
              not any(run in c for c in contents(one("GET", f"/v1/memories/search?q={run}", alice))))

        # ------------------------------------------------------------------------------------
        print(f"\n  {GREY}re-authorising history (9.4){RESET}")
        bsid = one("POST", "/v1/sessions", bob, {"title": "suite"})["body"]["session_id"]
        marker4 = f"Suite tool result {run}: restricted detail."
        one("POST", f"/v1/sessions/{bsid}/turns", bob, {"role": "tool", "content": marker4})
        check("a manager's tool turn is in his context while he is a manager",
              marker4 in rendered(context(bob, session_id=bsid)))
        try:
            core_range("arm_revoke_bob_manager")
            r = context(bob, session_id=bsid)
            check("demoted: the turn is dropped, and the block says why",
                  marker4 not in rendered(r) and "which you no longer hold" in rendered(r)
                  and r["body"]["omitted"] >= 1)
            set_setting("history.revalidate", "off")
            r = context(bob, session_id=bsid)
            check("demoted and revalidation off: the turn outlives the permission",
                  marker4 in rendered(r))
            check("and the log marks it as having outlived it",
                  mem_sql("SELECT count(*) FROM mem.context_log c, jsonb_array_elements(c.items) i "
                          f"WHERE c.id = '{r['body']['context_id']}' "
                          "AND (i->>'outlived_its_permission')::boolean") == "1")
            set_setting("history.revalidate", "on")
        finally:
            core_range("restore_bob_manager")
        check("restored: the turn is back in his context",
              marker4 in rendered(context(bob, session_id=bsid)))
    finally:
        restore_all()
        range_mem("retire_unapproved_rules")

    # ----------------------------------------------------------------------------------------
    print(f"\n  {GREY}the stores agree{RESET}")
    proc = compose("--profile", "memory", "run", "--rm", "--entrypoint",
                   "supportpilot-memory-reconcile", "memory-init", timeout=300)
    last = [l for l in proc.stdout.splitlines() if "[reconcile]" in l]
    check("memory-db and both vector layouts agree", proc.returncode == 0,
          last[-1].replace("[reconcile] ", "") if last else proc.stderr[:120])

    print()
    if failures:
        print(f"  {RED}{len(failures)} check(s) failed{RESET}\n")
        return 1
    print(f"  {GREEN}all checks passed{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
