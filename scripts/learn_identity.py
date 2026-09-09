"""Module 2 exercises — how a token string becomes a verified subject.

Runs the same in PowerShell and bash. Read it: the point is the mechanism, not the script.

    python scripts/learn_identity.py token            decode alice's token and show every claim
    python scripts/learn_identity.py forge            tamper with a claim and see the API respond
    python scripts/learn_identity.py audience         a valid token for the wrong service
    python scripts/learn_identity.py demote bob       take bob's manager role away, live
    python scripts/learn_identity.py promote bob      give it back
    python scripts/learn_identity.py whois bob        what the database says about someone
"""

from __future__ import annotations

import base64
import json
import ssl
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KEYCLOAK = "https://localhost:8443"
REALM = "supportpilot"

GREEN, RED, YELLOW, GREY, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[1m", "\033[0m"
)


def tls() -> ssl.SSLContext:
    context = ssl.create_default_context()
    certificate = REPO / ".secrets" / "tls" / "keycloak.crt"
    if certificate.exists():
        context.load_verify_locations(cafile=str(certificate))
    return context


def token_for(username: str, scope: str = "openid", client: str = "supportpilot-test-harness") -> str:
    data = urllib.parse.urlencode({
        "grant_type": "password", "client_id": client,
        "username": username, "password": f"{username}-local-password", "scope": scope,
    }).encode()
    url = f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token"
    with urllib.request.urlopen(url, data=data, timeout=20, context=tls()) as response:
        return json.load(response)["access_token"]


def part(segment: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))


def encode(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def call_api(path: str, token: str) -> tuple[int, str]:
    """Call the API from inside the app network — it has no host-published port."""
    probe = (
        "import json, os, httpx\n"
        "r = httpx.get('http://api:8000' + os.environ['P'],"
        " headers={'Authorization': 'Bearer ' + os.environ['T']}, timeout=20)\n"
        "print(json.dumps({'s': r.status_code, 'b': r.text[:120]}))\n"
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


# ------------------------------------------------------------------------------------------------
def cmd_token(who: str = "alice") -> None:
    raw = token_for(who)
    header, payload, signature = raw.split(".")

    print(f"\n{BOLD}The token {who} presents{RESET}")
    print("-" * 70)
    print(f"{BOLD}HEADER{RESET}  {GREY}(which key signed this, and how){RESET}")
    print(json.dumps(part(header), indent=2))

    claims = part(payload)
    print(f"\n{BOLD}PAYLOAD{RESET}  {GREY}(the claims){RESET}")
    print(json.dumps(claims, indent=2))

    print(f"\n{BOLD}SIGNATURE{RESET}  {GREY}{len(signature)} chars — over header+payload{RESET}")
    print(f"  {signature[:48]}...")

    print(f"\n{BOLD}What the API takes from this{RESET}")
    print(f"  {GREEN}sub{RESET}       {claims.get('sub')}   {GREY}<- the ONLY claim used for identity{RESET}")
    print(f"  {GREY}aud       {claims.get('aud')}{RESET}")
    print(f"  {GREY}iss       {claims.get('iss')}{RESET}")
    print(f"  {GREY}exp       {claims.get('exp')}  (expires in "
          f"{claims.get('exp', 0) - claims.get('iat', 0)}s){RESET}")

    print(f"\n{BOLD}What is NOT in the token, and is loaded from the database instead{RESET}")
    print(f"  {YELLOW}organization / tenant{RESET}   not present")
    print(f"  {YELLOW}support role{RESET}            "
          f"{'present as realm_access, and deliberately ignored' if claims.get('realm_access') else 'not present'}")
    print(f"\n  {GREY}The API calls load_subject(sub) and reads app.memberships on every request.{RESET}\n")


def cmd_forge() -> None:
    real = token_for("alice")
    header, payload, signature = real.split(".")
    claims = part(payload)

    print(f"\n{BOLD}Tampering with a claim, keeping the original signature{RESET}")
    print("-" * 70)
    print(f"  original sub : {claims['sub']}")

    claims["sub"] = "mallory-id"
    claims["realm_access"] = {"roles": ["administrator"]}
    forged = f"{header}.{encode(claims)}.{signature}"
    print(f"  forged   sub : {claims['sub']}  {GREY}+ realm_access.roles = [administrator]{RESET}")

    print(f"\n{BOLD}Both tokens against the same endpoint{RESET}")
    for label, token in (("real  ", real), ("forged", forged)):
        status, body = call_api("/v1/orders/ORD-2001", token)
        colour = GREEN if (status == 200) == (label.strip() == "real") else RED
        print(f"  {label} -> {colour}HTTP {status}{RESET}  {GREY}{body[:60]}{RESET}")

    print(f"\n  {GREY}The signature covers header+payload. Changing one byte of the payload{RESET}")
    print(f"  {GREY}invalidates it, and no amount of claiming to be someone else survives that.{RESET}\n")


def admin_token() -> str:
    password = (REPO / ".secrets" / "keycloak_admin_password").read_text(encoding="utf-8").strip()
    data = urllib.parse.urlencode({
        "grant_type": "password", "client_id": "admin-cli",
        "username": "kcadmin", "password": password,
    }).encode()
    url = f"{KEYCLOAK}/realms/master/protocol/openid-connect/token"
    with urllib.request.urlopen(url, data=data, timeout=20, context=tls()) as response:
        return json.load(response)["access_token"]


def ensure_other_service_client() -> str:
    """A second client in the same realm, with no SupportPilot audience mapper.

    This is the whole point of the audience check and it cannot be shown with one client: the
    scenario is two services trusting one identity provider. A token minted for the other service
    is completely valid — right issuer, right signature, right user — and must still be refused
    here. Created once, idempotently, purely as a teaching fixture.
    """
    name = "another-service"
    token = admin_token()

    def call(method: str, path: str, body: dict | None = None):
        request = urllib.request.Request(
            f"{KEYCLOAK}/admin/realms/{REALM}{path}", method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=20, context=tls()) as response:
            raw = response.read()
            return json.loads(raw) if raw else None

    if not call("GET", f"/clients?clientId={name}"):
        call("POST", "/clients", {
            "clientId": name,
            "name": "Another service in the same realm (teaching fixture)",
            "enabled": True, "publicClient": True,
            "standardFlowEnabled": False, "directAccessGrantsEnabled": True,
            "defaultClientScopes": ["basic", "acr", "profile", "email", "roles"],
        })
    return name


def cmd_audience() -> None:
    print()
    print(f"{BOLD}A valid token, minted for a different audience{RESET}")
    print("-" * 70)

    good = token_for("alice", scope="openid")
    print(f"  a token for supportpilot-api    aud = {part(good.split('.')[1]).get('aud')}")
    status, _ = call_api("/v1/orders/ORD-2001", good)
    print(f"    -> {GREEN if status == 200 else RED}HTTP {status}{RESET}")

    client = ensure_other_service_client()
    other = token_for("alice", scope="openid", client=client)
    print()
    print(f"a token for {client}      aud = {part(other.split('.')[1]).get('aud')}")
    print(f"  {GREY}same realm, same signing key, same user — alice really did authenticate{RESET}")
    status, body = call_api("/v1/orders/ORD-2001", other)
    print(f"    -> {GREEN if status == 401 else RED}HTTP {status}{RESET}  {GREY}{body[:60]}{RESET}")

    print()
    print(f"{BOLD}Why this one matters{RESET}")
    print(f"  {GREY}Both tokens are genuine. The second states who alice is just as truthfully{RESET}")
    print(f"  {GREY}as the first. The only difference is who it was minted FOR.{RESET}")
    print(f"  {GREY}Skip this check and every service that can issue a token to a user becomes{RESET}")
    print(f"  {GREY}a key to every other service trusting the same identity provider.{RESET}")
    print()


def cmd_whois(username: str) -> None:
    rows = sql(
        "SELECT u.identity_subject || '  |  ' || u.display_name || '  |  ' "
        "|| coalesce(o.slug,'(none)') || '  |  ' || coalesce(m.role,'(none)') "
        "|| '  |  ' || coalesce(m.status,'-') "
        "FROM app.users u LEFT JOIN app.memberships m ON m.user_id = u.id "
        "LEFT JOIN app.organizations o ON o.id = m.organization_id "
        f"WHERE u.identity_subject = '{username}-id'"
    )
    print(f"\n{BOLD}What the database says — this is what authorization uses{RESET}")
    print("-" * 70)
    print("  subject     |  name  |  tenant  |  role  |  status")
    for row in rows.splitlines():
        print(f"  {row}")
    print()


def cmd_role(username: str, role: str) -> None:
    sql(
        f"UPDATE app.memberships SET role = '{role}' "
        f"WHERE user_id = (SELECT id FROM app.users WHERE identity_subject = '{username}-id')"
    )
    print(f"\n  {GREEN}{username} is now {role}{RESET} in the database.")
    print(f"  {GREY}Any token already issued to them is untouched and still valid.{RESET}")
    print(f"  {GREY}Ask the agent something in the SAME Onyx session and watch what changes.{RESET}\n")


COMMANDS = {"token", "forge", "audience", "demote", "promote", "whois"}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return 1
    command = sys.argv[1]
    who = sys.argv[2] if len(sys.argv) > 2 else "alice"

    if command == "token":
        cmd_token(who)
    elif command == "forge":
        cmd_forge()
    elif command == "audience":
        cmd_audience()
    elif command == "whois":
        cmd_whois(who)
    elif command == "demote":
        cmd_role(who, "support_agent")
    elif command == "promote":
        cmd_role(who, "support_manager")
    return 0


if __name__ == "__main__":
    sys.exit(main())
