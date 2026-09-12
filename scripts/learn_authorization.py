"""Module 3 exercises — policy as code.

    python scripts/learn_authorization.py input      the exact input and decision, from OPA's log
    python scripts/learn_authorization.py matrix     every user against every resource, as a grid
    python scripts/learn_authorization.py fields     obligations: the same record, two roles
    python scripts/learn_authorization.py outage     stop OPA mid-flight and watch what happens
    python scripts/learn_authorization.py break      install a policy that allows cross-tenant reads
    python scripts/learn_authorization.py restore    put the real policy back

`break` edits the policy bundle and reloads OPA. It is reverted by `restore`, which also re-runs the
policy tests. Run `restore` before doing anything else with the lab.
"""

from __future__ import annotations

import json
import shutil
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
POLICY = REPO / "policy" / "supportpilot" / "authz.rego"
BACKUP = REPO / "policy" / "supportpilot" / ".authz.rego.original"
KEYCLOAK = "https://localhost:8443"
REALM = "supportpilot"

CEDAR = "11111111-1111-1111-1111-111111111111"
NORTHWIND = "22222222-2222-2222-2222-222222222222"

GREEN, RED, YELLOW, GREY, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[1m", "\033[0m"
)


def tls() -> ssl.SSLContext:
    context = ssl.create_default_context()
    certificate = REPO / ".secrets" / "tls" / "keycloak.crt"
    if certificate.exists():
        context.load_verify_locations(cafile=str(certificate))
    return context


def token_for(username: str) -> str:
    data = urllib.parse.urlencode({
        "grant_type": "password", "client_id": "supportpilot-test-harness",
        "username": username, "password": f"{username}-local-password", "scope": "openid",
    }).encode()
    url = f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token"
    with urllib.request.urlopen(url, data=data, timeout=20, context=tls()) as response:
        return json.load(response)["access_token"]


def call_api(path: str, token: str) -> tuple[int, str]:
    probe = (
        "import json, os, httpx\n"
        "try:\n"
        "    r = httpx.get('http://api:8000' + os.environ['P'],"
        " headers={'Authorization': 'Bearer ' + os.environ['T']}, timeout=25)\n"
        "    print(json.dumps({'s': r.status_code, 'b': r.text[:300]}))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'s': 0, 'b': repr(exc)}))\n"
    )
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "-e", f"P={path}", "-e", f"T={token}",
         "approval-portal", "python", "-c", probe],
        cwd=REPO, capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace",
    )
    line = next((l for l in proc.stdout.splitlines() if l.startswith("{")), None)
    if not line:
        raise SystemExit(f"{RED}probe failed:{RESET} {(proc.stderr or proc.stdout)[:200]}")
    result = json.loads(line)
    return result["s"], result["b"]


def compose(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", *args], cwd=REPO,
                          capture_output=True, text=True, timeout=timeout)


def last_decision(resource_id: str | None = None, subject_id: str | None = None) -> dict | None:
    """The most recent decision matching an exact resource and an exact subject.

    Correlate precisely, or say nothing. This went wrong twice:

      1. The first version returned whatever decision was last in the log and presented it as the
         decision for the call just made. It reported "policy said allow" for a request the policy
         had never been asked about; the allow belonged to another user.
      2. The second filtered on "the subject belongs to cedar", which also matched a service account
         holding membership in cedar *and* northwind. Narrower, still wrong.

    Matching the subject id is the only version that answers the question actually being asked:
    what did the policy decide for *this* caller about *this* resource.
    """
    logs = compose("logs", "opa", "--tail", "120").stdout
    for line in reversed(logs.splitlines()):
        start = line.find('{"decision_id')
        if start < 0:
            continue
        try:
            decision = json.loads(line[start:])
        except json.JSONDecodeError:
            continue
        payload = decision.get("input") or {}
        if resource_id and (payload.get("resource") or {}).get("id") != resource_id:
            continue
        if subject_id and (payload.get("subject") or {}).get("id") != subject_id:
            continue
        return decision
    return None


# ------------------------------------------------------------------------------------------------
def cmd_input() -> None:
    alice = token_for("alice")
    call_api("/v1/customers/CUS-4003", alice)
    time.sleep(2)
    decision = last_decision()
    if not decision:
        raise SystemExit(f"{RED}no decision found in OPA's log{RESET}")

    print()
    print(f"{BOLD}What the API asked{RESET}  {GREY}— every field built server-side{RESET}")
    print("-" * 78)
    print(json.dumps(decision.get("input"), indent=2, ensure_ascii=False))
    print()
    print(f"{BOLD}What the policy answered{RESET}")
    print("-" * 78)
    print(json.dumps(decision.get("result"), indent=2, ensure_ascii=False))
    print()
    print(f"  {GREY}Nothing in the input came from the model, the chat, or the request body.{RESET}")
    print(f"  {GREY}The resource was loaded from the database before the question was asked —{RESET}")
    print(f"  {GREY}you cannot decide about a thing you have not looked at.{RESET}")
    print()


def cmd_matrix() -> None:
    """Every user against every resource. This is a consulting deliverable, not a debug tool."""
    users = ["alice", "bob", "fiona", "dana", "mallory"]
    probes = [
        ("ORD-2001", "/v1/orders/ORD-2001", "cedar order"),
        ("ORD-3001", "/v1/orders/ORD-3001", "northwind order"),
        ("TKT-1001", "/v1/tickets/TKT-1001", "cedar ticket"),
        ("CUS-4001", "/v1/customers/CUS-4001", "cedar customer"),
        ("CUS-4003", "/v1/customers/CUS-4003", "cedar, restricted"),
    ]

    print()
    print(f"{BOLD}Authorization matrix{RESET}  {GREY}200 = allowed, 404 = refused{RESET}")
    print("-" * 78)
    header = f"  {'':25}" + "".join(f"{u:>10}" for u in users)
    print(header)
    print("  " + "-" * (25 + 10 * len(users)))

    tokens = {u: token_for(u) for u in users}
    for label, path, description in probes:
        row = f"  {label} {GREY}{description:<16}{RESET}"
        cells = ""
        for user in users:
            status, _ = call_api(path, tokens[user])
            colour = GREEN if status == 200 else GREY
            cells += f"{colour}{status:>10}{RESET}"
        print(row + cells)

    print()
    print(f"  {GREY}Read the columns, not the cells. mallory is northwind — everything cedar is{RESET}")
    print(f"  {GREY}closed to her. fiona approves refunds and cannot read orders: approving and{RESET}")
    print(f"  {GREY}seeing are separate powers, which is what separation of duty means here.{RESET}")
    print()


def cmd_fields() -> None:
    """Obligations: allow is not the whole answer."""
    print()
    print(f"{BOLD}The same customer, two roles{RESET}  {GREY}CUS-4003 is marked restricted{RESET}")
    print("-" * 78)
    for user in ("alice", "bob"):
        status, body = call_api("/v1/customers/CUS-4003", token_for(user))
        try:
            fields = sorted(json.loads(body).keys())
        except Exception:
            fields = [body[:40]]
        has_email = "email" in fields
        mark = f"{RED}email present{RESET}" if has_email else f"{GREEN}no email{RESET}"
        print(f"  {user:6} ({'support_agent' if user == 'alice' else 'support_manager':16}) "
              f"HTTP {status}  {mark}")
        print(f"         {GREY}{', '.join(fields)}{RESET}")

    print()
    print(f"  {GREY}Same endpoint, same code path, same database row. The difference is an{RESET}")
    print(f"  {GREY}obligation the policy attached to its allow: a list of permitted fields,{RESET}")
    print(f"  {GREY}which the API applies before the response is built.{RESET}")
    print()
    print(f"  {GREY}Without obligations the choice is all-or-nothing: either an agent sees{RESET}")
    print(f"  {GREY}restricted customers completely, or cannot work their tickets at all.{RESET}")
    print()


def cmd_outage() -> None:
    alice = token_for("alice")
    print()
    print(f"{BOLD}Stopping the policy service mid-flight{RESET}")
    print("-" * 78)
    status, _ = call_api("/v1/orders/ORD-2001", alice)
    print(f"  before   ORD-2001 -> {GREEN if status == 200 else RED}HTTP {status}{RESET}")

    compose("stop", "opa")
    try:
        status, body = call_api("/v1/orders/ORD-2001", alice)
        verdict = f"{GREEN}refused{RESET}" if status != 200 else f"{RED}STILL ALLOWED{RESET}"
        print(f"  OPA down ORD-2001 -> HTTP {status}  {verdict}  {GREY}{body[:50]}{RESET}")
        print()
        if status == 503:
            print(f"  {GREY}503, not 404. An outage is reported as an outage — reporting it as{RESET}")
            print(f"  {GREY}'not found' would hide a broken dependency behind a normal answer.{RESET}")
        elif status == 200:
            print(f"  {RED}A cached or fallback allow exists. That is the finding.{RESET}")
    finally:
        compose("start", "opa")
        for _ in range(15):
            time.sleep(2)
            if call_api("/v1/orders/ORD-2001", alice)[0] == 200:
                break
        print(f"\n  {GREEN}OPA restarted{RESET}")
    print()


BAD_RULE = '''

# ================================================================================================
# DELIBERATELY WRONG — installed by scripts/learn_authorization.py, removed by `restore`.
#
# A plausible mistake: someone writes the tenant check against the subject's own organisation list
# instead of comparing it to the resource, so it is true for anybody who belongs to any tenant.
# ================================================================================================
decision := allow_with("same_organization_and_allowed_role", {"allowed_fields": order_fields}) if {
	input.action == "order.read"
	count(input.subject.organizations) > 0
	any_role(read_roles)
}
'''


def alice_subject_id() -> str:
    """alice's application user id — the value that appears as subject.id in the policy input."""
    password = (REPO / ".secrets" / "postgres_bootstrap_password").read_text(encoding="utf-8").strip()
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "-e", f"PGPASSWORD={password}", "postgres",
         "psql", "-U", "supportpilot_admin", "-d", "supportpilot", "-tAX",
         "-c", "SELECT id::text FROM app.users WHERE identity_subject = 'alice-id'"],
        cwd=REPO, capture_output=True, text=True, timeout=60, encoding="utf-8",
    )
    return proc.stdout.strip()


def cmd_break() -> None:
    if not BACKUP.exists():
        shutil.copy(POLICY, BACKUP)
    text = POLICY.read_text(encoding="utf-8")
    if "DELIBERATELY WRONG" in text:
        print(f"\n  {YELLOW}the broken rule is already installed{RESET}\n")
    else:
        POLICY.write_text(text + BAD_RULE, encoding="utf-8")
    compose("restart", "opa")
    time.sleep(6)

    print()
    print(f"{BOLD}A policy that no longer checks the tenant{RESET}")
    print("-" * 78)
    alice = token_for("alice")
    status, body = call_api("/v1/orders/ORD-3001", alice)
    print(f"  alice -> ORD-3001 (northwind)   HTTP {status}  {GREY}{body[:60]}{RESET}")

    time.sleep(2)
    decision = last_decision(resource_id="ORD-3001", subject_id=alice_subject_id())

    print()
    if status == 200:
        print(f"  {RED}The order was returned. One broken rule was enough.{RESET}")
    elif decision is None:
        print(f"  {GREEN}Refused — and the policy was never even consulted.{RESET}")
        print()
        print(f"  {GREY}No decision for ORD-3001 on behalf of a cedar subject appears in OPA's{RESET}")
        print(f"  {GREY}log at all. The resource lookup runs first and is scoped to the caller's{RESET}")
        print(f"  {GREY}own memberships, so it found nothing and there was nothing to ask about.{RESET}")
        print()
        print(f"  {BOLD}The broken rule was irrelevant. An earlier layer had already stopped it.{RESET}")
        print(f"  {GREY}Check the reason in the audit trail — it will say resource_not_visible,{RESET}")
        print(f"  {GREY}not a policy reason, which is how you tell which layer acted.{RESET}")
    else:
        result = decision.get("result") or {}
        print(f"  {YELLOW}Policy allowed it (reason={result.get('reason')}) and the request still{RESET}")
        print(f"  {YELLOW}failed — so a layer after the policy refused.{RESET}")
    print()
    print(f"  {BOLD}Run `restore` before anything else.{RESET}")
    print()


def cmd_restore() -> None:
    if BACKUP.exists():
        shutil.copy(BACKUP, POLICY)
        BACKUP.unlink()
        print(f"\n  {GREEN}policy restored from backup{RESET}")
    elif "DELIBERATELY WRONG" in POLICY.read_text(encoding="utf-8"):
        text = POLICY.read_text(encoding="utf-8")
        POLICY.write_text(text[:text.index("\n\n# " + "=" * 96)], encoding="utf-8")
        print(f"\n  {GREEN}broken rule removed{RESET}")
    else:
        print(f"\n  {GREY}policy already clean{RESET}")

    compose("restart", "opa")
    time.sleep(6)

    result = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{REPO / 'policy'}:/policy",
         "openpolicyagent/opa:1.4.2", "test", "/policy/supportpilot", "/policy/tests"],
        capture_output=True, text=True, timeout=300,
    )
    tail = (result.stdout or result.stderr).strip().splitlines()[-1:]
    print(f"  policy tests: {GREEN if result.returncode == 0 else RED}{' '.join(tail)}{RESET}\n")


COMMANDS = {
    "input": cmd_input, "matrix": cmd_matrix, "fields": cmd_fields,
    "outage": cmd_outage, "break": cmd_break, "restore": cmd_restore,
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return 1
    COMMANDS[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
