"""Module 2b — what a service account actually costs.

Architecture A is the most common way agents are wired, and the reason is ordinary: it is the
easiest. The agent gets one credential, uses it for every call, and the API is simple because it
only ever talks to one caller.

The cost is not obvious from a diagram, so this builds one and measures it.

A service account must serve every user of the system. So it needs the *union* of every user's
permissions — it has to be able to read cedar's data for alice and northwind's data for mallory.
That union is what every single request then runs with, including a request that a customer
steered by writing a sentence into a support ticket.

    python scripts/learn_service_account.py build      create the service account
    python scripts/learn_service_account.py compare    alice vs the service account, same API
    python scripts/learn_service_account.py audit      what the evidence looks like either way
    python scripts/learn_service_account.py remove     delete it again

Nothing here weakens SupportPilot. The service account is an ordinary user with wide membership —
which is precisely the point being demonstrated.
"""

from __future__ import annotations

import json
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KEYCLOAK = "https://localhost:8443"
REALM = "supportpilot"

ACCOUNT = "agent-service"
PASSWORD = "agent-service-local-password"

GREEN, RED, YELLOW, GREY, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[1m", "\033[0m"
)


def tls() -> ssl.SSLContext:
    context = ssl.create_default_context()
    certificate = REPO / ".secrets" / "tls" / "keycloak.crt"
    if certificate.exists():
        context.load_verify_locations(cafile=str(certificate))
    return context


def admin_token() -> str:
    password = (REPO / ".secrets" / "keycloak_admin_password").read_text(encoding="utf-8").strip()
    data = urllib.parse.urlencode({
        "grant_type": "password", "client_id": "admin-cli",
        "username": "kcadmin", "password": password,
    }).encode()
    url = f"{KEYCLOAK}/realms/master/protocol/openid-connect/token"
    with urllib.request.urlopen(url, data=data, timeout=20, context=tls()) as response:
        return json.load(response)["access_token"]


def kc(method: str, path: str, body: dict | None = None, token: str | None = None):
    token = token or admin_token()
    request = urllib.request.Request(
        f"{KEYCLOAK}/admin/realms/{REALM}{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20, context=tls()) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def token_for(username: str, password: str) -> str:
    data = urllib.parse.urlencode({
        "grant_type": "password", "client_id": "supportpilot-test-harness",
        "username": username, "password": password, "scope": "openid",
    }).encode()
    url = f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token"
    with urllib.request.urlopen(url, data=data, timeout=20, context=tls()) as response:
        return json.load(response)["access_token"]


def sql(statement: str) -> str:
    password = (REPO / ".secrets" / "postgres_bootstrap_password").read_text(encoding="utf-8").strip()
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "-e", f"PGPASSWORD={password}", "postgres",
         "psql", "-U", "supportpilot_admin", "-d", "supportpilot", "-tAX", "-c", statement],
        cwd=REPO, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise SystemExit(f"{RED}{(proc.stderr or proc.stdout).strip()[:200]}{RESET}")
    return proc.stdout.strip()


def call_api(path: str, token: str) -> tuple[int, str]:
    probe = (
        "import json, os, httpx\n"
        "r = httpx.get('http://api:8000' + os.environ['P'],"
        " headers={'Authorization': 'Bearer ' + os.environ['T']}, timeout=20)\n"
        "print(json.dumps({'s': r.status_code, 'b': r.text[:200]}))\n"
    )
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "-e", f"P={path}", "-e", f"T={token}",
         "approval-portal", "python", "-c", probe],
        cwd=REPO, capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace",
    )
    line = next((l for l in proc.stdout.splitlines() if l.startswith("{")), None)
    if not line:
        raise SystemExit(f"{RED}probe failed:{RESET} {(proc.stderr or proc.stdout)[:200]}")
    result = json.loads(line)
    return result["s"], result["b"]


# ------------------------------------------------------------------------------------------------
def cmd_build() -> None:
    print()
    print(f"{BOLD}Building the service account{RESET}")
    print("-" * 78)

    token = admin_token()
    existing = kc("GET", f"/users?username={ACCOUNT}", token=token)
    if not existing:
        kc("POST", "/users", {
            "username": ACCOUNT, "id": f"{ACCOUNT}-id", "enabled": True, "emailVerified": True,
            "email": f"{ACCOUNT}@supportpilot.invalid",
            "firstName": "Agent", "lastName": "Service",
            "credentials": [{"type": "password", "value": PASSWORD, "temporary": False}],
            "realmRoles": [f"default-roles-{REALM}"],
        }, token=token)
        print(f"  {GREEN}created{RESET} Keycloak user '{ACCOUNT}'")
    else:
        print(f"  {GREY}Keycloak user '{ACCOUNT}' already exists{RESET}")

    role = kc("GET", f"/roles/default-roles-{REALM}", token=token)
    user = kc("GET", f"/users?username={ACCOUNT}", token=token)[0]
    held = {r["name"] for r in kc("GET", f"/users/{user['id']}/role-mappings/realm", token=token) or []}
    if f"default-roles-{REALM}" not in held:
        kc("POST", f"/users/{user['id']}/role-mappings/realm", [role], token=token)

    # Keycloak assigns its own id on user creation and ignores one supplied in the body — unlike a
    # realm import, which honours it. The token's `sub` is therefore a generated UUID, and that is
    # what app.users.identity_subject must hold, or the lookup finds nobody.
    subject = user["id"]
    sql(
        "INSERT INTO app.users (id, identity_subject, display_name) VALUES "
        f"('5e111111-1111-1111-1111-111111111111', '{subject}', 'SupportPilot Agent (service)') "
        f"ON CONFLICT (id) DO UPDATE SET identity_subject = '{subject}'"
    )
    print(f"  {GREY}Keycloak assigned sub = {subject}{RESET}")

    # The decisive step. A service account serves every user, so it must be able to reach every
    # user's data — which means membership in every tenant, with the widest role in each.
    for tenant, role_name in (("cedar", "support_manager"), ("northwind", "support_manager")):
        sql(
            "INSERT INTO app.memberships (user_id, organization_id, role) SELECT "
            "'5e111111-1111-1111-1111-111111111111', o.id, "
            f"'{role_name}' FROM app.organizations o WHERE o.slug = '{tenant}' "
            "ON CONFLICT (user_id, organization_id, role) DO UPDATE SET status = 'active'"
        )
    print(f"  {GREEN}granted{RESET} membership in cedar AND northwind, as support_manager in both")
    print()
    print(f"  {YELLOW}That breadth is not a mistake — it is the requirement.{RESET}")
    print(f"  {GREY}A single credential that answers for every user must be able to reach{RESET}")
    print(f"  {GREY}everything any of them could. There is no narrower version of it.{RESET}")
    print()
    print(f"  Next: {BOLD}python scripts/learn_service_account.py compare{RESET}")
    print()


def cmd_compare() -> None:
    print()
    print(f"{BOLD}The same API, two callers{RESET}")
    print("-" * 78)

    try:
        service = token_for(ACCOUNT, PASSWORD)
    except urllib.error.HTTPError:
        raise SystemExit(f"{RED}run 'build' first{RESET}")
    alice = token_for("alice", "alice-local-password")

    targets = [
        ("ORD-2001", "cedar's order"),
        ("ORD-3001", "northwind's order"),
    ]
    print(f"  {'':28} {'alice':>10}   {'service account':>18}")
    observed = {}
    for order, label in targets:
        a_status, _ = call_api(f"/v1/orders/{order}", alice)
        s_status, _ = call_api(f"/v1/orders/{order}", service)
        observed[order] = (a_status, s_status)
        a_text = f"{GREEN}200{RESET}" if a_status == 200 else f"{YELLOW}{a_status}{RESET}"
        s_text = f"{RED}200{RESET}" if s_status == 200 else f"{GREEN}{s_status}{RESET}"
        print(f"  {order}  {label:18} {a_text:>20}   {s_text:>26}")

    print()
    # Stated from the measurement, not asserted ahead of it. An earlier version of this script
    # printed the expected conclusion regardless of what the calls returned, and was wrong.
    alice_cross = observed["ORD-3001"][0] == 200
    service_cross = observed["ORD-3001"][1] == 200
    if service_cross and not alice_cross:
        print(f"  {BOLD}alice cannot cross the tenant line. The service account can.{RESET}")
    elif not service_cross and not alice_cross:
        print(f"  {YELLOW}Neither crossed the tenant line — the service account is not set up{RESET}")
        print(f"  {YELLOW}correctly, so this run demonstrates nothing. Re-run 'build'.{RESET}")
    else:
        print(f"  {RED}Unexpected: alice crossed the tenant line. Investigate before reading on.{RESET}")
    print()
    print(f"  {GREY}In architecture A every request the agent makes — for alice, for mallory,{RESET}")
    print(f"  {GREY}for a request steered by text a customer wrote into a ticket — runs with{RESET}")
    print(f"  {GREY}the second column's reach, not the first's.{RESET}")
    print()

    # Customer search makes the blast radius concrete rather than theoretical.
    _, a_body = call_api("/v1/customers?q=ar&limit=50", alice)
    _, s_body = call_api("/v1/customers?q=ar&limit=50", service)
    try:
        a_count = len(json.loads(a_body).get("results", []))
        s_count = len(json.loads(s_body).get("results", []))
        print(f"  customer search for 'ar':   alice sees {a_count}, "
              f"the service account sees {s_count} {GREY}(across both tenants){RESET}")
        print()
    except Exception:
        pass


def cmd_audit() -> None:
    print()
    print(f"{BOLD}What the evidence says afterwards{RESET}")
    print("-" * 78)
    rows = sql(
        "SELECT coalesce(u.display_name, a.actor_id) || ' | ' || a.action || ' | ' || a.decision "
        "FROM app.audit_events a LEFT JOIN app.users u ON u.id::text = a.actor_id "
        "WHERE a.actor_type = 'user' ORDER BY a.occurred_at DESC LIMIT 8"
    )
    for row in rows.splitlines():
        actor = row.split("|")[0].strip()
        colour = RED if "service" in actor.lower() else GREEN
        print(f"  {colour}{row.strip()}{RESET}")
    print()
    print(f"  {GREY}Rows naming a person answer 'who did this'. Rows naming the service account{RESET}")
    print(f"  {GREY}record only that the agent did something — which is the one question nobody{RESET}")
    print(f"  {GREY}asks an audit trail, because it is already known.{RESET}")
    print()


def cmd_remove() -> None:
    sql("DELETE FROM app.memberships WHERE user_id = '5e111111-1111-1111-1111-111111111111'")
    sql("DELETE FROM app.users WHERE identity_subject = 'agent-service-id'")
    try:
        token = admin_token()
        for user in kc("GET", f"/users?username={ACCOUNT}", token=token) or []:
            kc("DELETE", f"/users/{user['id']}", token=token)
    except Exception:
        pass
    print(f"\n  {GREEN}service account removed{RESET}\n")


COMMANDS = {"build": cmd_build, "compare": cmd_compare, "audit": cmd_audit, "remove": cmd_remove}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return 1
    COMMANDS[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
