"""Connect a running Onyx to SupportPilot (P1-04, P1-16).

Does the half that can be automated, and prints the exact values for the half that cannot.

Automated here:
  * joins Onyx's api_server to the SupportPilot `app` network, so it can reach http://api:8000;
  * generates a client secret into .secrets/ and configures the Keycloak `onyx-web` client as a
    confidential client with Onyx's real callback URI;
  * verifies the discovery document Onyx will fetch resolves to endpoints Onyx can actually reach.

Left to you, because both need an Onyx admin login this script does not have:
  * creating the SSO provider row (Admin Panel -> Organization -> SSO Providers);
  * registering the action with passthrough auth (Admin Panel -> Actions).
The exact field values are printed at the end.

Run: python scripts/connect_onyx.py
"""

from __future__ import annotations

import base64
import json
import secrets
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KEYCLOAK = "http://localhost:8080"
REALM = "supportpilot"
CLIENT_ID = "onyx-web"
PROVIDER_NAME = "keycloak"
ONYX_WEB = "http://localhost:3000"
ONYX_API_CONTAINER = "onyx-api_server-1"
APP_NETWORK = "supportpilot_app"

GREEN, RED, YELLOW, GREY, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[1m", "\033[0m"
)


def step(message: str) -> None:
    print(f"{YELLOW}==>{RESET} {message}")


def ok(message: str) -> None:
    print(f"    {GREEN}ok{RESET}  {message}")


def warn(message: str) -> None:
    print(f"    {YELLOW}!!{RESET}  {message}")


def fail(message: str) -> None:
    raise SystemExit(f"    {RED}fail{RESET}  {message}")


def run(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, cwd=REPO, capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace",
    )


# ------------------------------------------------------------------------------------------------
# Keycloak admin API
# ------------------------------------------------------------------------------------------------
def admin_token() -> str:
    password = (REPO / ".secrets" / "keycloak_admin_password").read_text(encoding="utf-8").strip()
    data = urllib.parse.urlencode({
        "grant_type": "password", "client_id": "admin-cli",
        "username": "kcadmin", "password": password,
    }).encode()
    url = f"{KEYCLOAK}/realms/master/protocol/openid-connect/token"
    with urllib.request.urlopen(url, data=data, timeout=20) as response:
        return json.load(response)["access_token"]


def admin_request(method: str, path: str, token: str, body: dict | None = None):
    request = urllib.request.Request(
        f"{KEYCLOAK}/admin/realms/{REALM}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        fail(f"Keycloak admin {method} {path} -> {error.code} {error.read()[:200]!r}")


def main() -> int:
    print()
    print(f"{BOLD}Connecting Onyx to SupportPilot{RESET}")
    print("-" * 74)

    # --- 1. Onyx must be running -------------------------------------------------------------
    step("Checking Onyx is running")
    state = run(["docker", "inspect", "-f", "{{.State.Status}}", ONYX_API_CONTAINER]).stdout.strip()
    if state != "running":
        fail(
            f"{ONYX_API_CONTAINER} is '{state or 'absent'}'. Start Onyx first:\n"
            "        docker compose -f docker-compose.yml -f docker-compose.onyx-lite.yml up -d"
        )
    ok(f"{ONYX_API_CONTAINER} is running")

    # --- 2. Network --------------------------------------------------------------------------
    step("Joining Onyx to the SupportPilot app network")
    networks = run(
        ["docker", "inspect", "-f", "{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}",
         ONYX_API_CONTAINER]
    ).stdout.split()
    if APP_NETWORK in networks:
        ok(f"already attached to {APP_NETWORK}")
    else:
        result = run(["docker", "network", "connect", APP_NETWORK, ONYX_API_CONTAINER])
        if result.returncode != 0:
            fail(result.stderr.strip()[:200])
        ok(f"attached to {APP_NETWORK}")

    probe = run([
        "docker", "exec", ONYX_API_CONTAINER, "python", "-c",
        "import urllib.request;print(urllib.request.urlopen('http://api:8000/healthz',timeout=8).status)",
    ])
    if "200" not in probe.stdout:
        fail(f"Onyx still cannot reach http://api:8000 — {(probe.stderr or probe.stdout)[:160]}")
    ok("Onyx can reach http://api:8000")

    # --- 3. Keycloak client ------------------------------------------------------------------
    step("Configuring the Keycloak client")
    secret_path = REPO / ".secrets" / "onyx_oauth_client_secret"
    if secret_path.exists() and secret_path.read_text(encoding="utf-8").strip():
        client_secret = secret_path.read_text(encoding="utf-8").strip()
        ok("using the existing client secret from .secrets/")
    else:
        client_secret = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        secret_path.write_text(client_secret, encoding="utf-8", newline="")
        ok("generated a client secret into .secrets/onyx_oauth_client_secret")

    token = admin_token()
    clients = admin_request("GET", f"/clients?clientId={CLIENT_ID}", token)
    if not clients:
        fail(f"client '{CLIENT_ID}' not found in realm '{REALM}'")
    client = clients[0]

    callback = f"{ONYX_WEB}/api/auth/oidc/{PROVIDER_NAME}/callback"
    client.update({
        "publicClient": False,
        "secret": client_secret,
        "standardFlowEnabled": True,
        "redirectUris": sorted({*client.get("redirectUris", []), callback,
                                f"{ONYX_WEB}/auth/oidc/callback"}),
        "webOrigins": sorted({*client.get("webOrigins", []), ONYX_WEB}),
    })
    admin_request("PUT", f"/clients/{client['id']}", token, client)
    ok(f"{CLIENT_ID} is confidential, with redirect URI {callback}")

    # Keycloak stores the secret separately from the representation on some versions; read it back
    # rather than assuming the PUT took.
    stored = admin_request("GET", f"/clients/{client['id']}/client-secret", token)
    if stored.get("value") != client_secret:
        admin_request("POST", f"/clients/{client['id']}/client-secret", token)
        stored = admin_request("GET", f"/clients/{client['id']}/client-secret", token)
        secret_path.write_text(stored["value"], encoding="utf-8", newline="")
        client_secret = stored["value"]
        warn("Keycloak regenerated the secret; .secrets/ updated to match")
    ok("client secret verified against Keycloak")

    # --- 4. Discovery reachability -----------------------------------------------------------
    step("Checking the discovery document Onyx will use")
    discovery = f"http://keycloak:8080/realms/{REALM}/.well-known/openid-configuration"
    result = run([
        "docker", "exec", ONYX_API_CONTAINER, "python", "-c",
        f"import urllib.request,json;d=json.load(urllib.request.urlopen('{discovery}',timeout=8));"
        "print(json.dumps({k:d[k] for k in ('issuer','authorization_endpoint','token_endpoint')}))",
    ])
    line = next((l for l in result.stdout.splitlines() if l.startswith("{")), None)
    if not line:
        fail(f"Onyx cannot fetch the discovery document: {(result.stderr or result.stdout)[:200]}")
    endpoints = json.loads(line)

    # This split is the whole reason the integration works without editing hosts files:
    # KC_HOSTNAME_BACKCHANNEL_DYNAMIC makes Keycloak advertise a browser-facing authorization
    # endpoint and a container-reachable token endpoint from the same document.
    if "localhost" not in endpoints["authorization_endpoint"]:
        warn("the authorization endpoint is not on localhost; the browser may not reach it")
    if "keycloak:8080" not in endpoints["token_endpoint"]:
        warn("the token endpoint is not container-reachable; check KC_HOSTNAME_BACKCHANNEL_DYNAMIC")
    ok(f"issuer        {endpoints['issuer']}")
    ok(f"browser  ->   {endpoints['authorization_endpoint']}")
    ok(f"Onyx     ->   {endpoints['token_endpoint']}")

    # --- 5. What you must do in the Onyx admin UI --------------------------------------------
    action_document = (REPO / "openapi" / "supportpilot-actions.yaml")
    print()
    print("-" * 74)
    print(f"{BOLD}Keycloak and networking are ready. Two steps remain in the Onyx admin UI.{RESET}")
    print(f"{GREY}Both need an Onyx admin login, which this script does not have.{RESET}")
    print()
    print(f"{BOLD}1. Admin Panel -> Organization -> SSO Providers -> add OIDC{RESET}")
    print(f"     name               {PROVIDER_NAME}")
    print(f"     openid_config_url  {discovery}")
    print(f"     client_id          {CLIENT_ID}")
    print(f"     client_secret      {client_secret}")
    print(f"     scopes             openid profile email")
    print(f"   {GREY}Callback to allowlist (already added to Keycloak): {callback}{RESET}")
    print(f"   {GREY}Login link becomes: {ONYX_WEB}/api/auth/oidc/{PROVIDER_NAME}/authorize{RESET}")
    print()
    print(f"{BOLD}2. Admin Panel -> Actions -> Add OpenAPI Action{RESET}")
    print(f"     schema             paste {action_document.relative_to(REPO)}")
    print(f"     {BOLD}Pass through user's OAuth token: ON{RESET}")
    print(f"   {GREY}This is the setting that matters. Onyx forwards the Keycloak access token from{RESET}")
    print(f"   {GREY}the user's login as `Authorization: Bearer ...`, which is what FR-02 requires.{RESET}")
    print(f"   {GREY}Leave custom headers empty: Onyx refuses passthrough combined with them.{RESET}")
    print()
    print(f"{BOLD}Then sign in to Onyx as alice (password alice-local-password) via Keycloak{RESET}")
    print(f"and run:  python scripts/verify_onyx_flow.py")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
