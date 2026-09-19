"""Bring up the SupportPilot local environment from a clean machine.

Generates local secrets if absent, builds images, starts services, and waits for the migration job
and the API to be ready. Safe to re-run: existing secrets are left alone so the database keeps
working.

Bootstrap succeeding is not the same as the environment being correct. Run verify_local.py after.
"""

from __future__ import annotations

import argparse
import base64
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SECRETS_DIR = REPO / ".secrets"

GREEN, RED, GREY, YELLOW, RESET = "\033[32m", "\033[31m", "\033[90m", "\033[33m", "\033[0m"

SECRET_NAMES = [
    "postgres_bootstrap_password",
    "migrator_db_password",
    "api_db_password",
    "worker_db_password",
    "auditor_db_password",
    "range_db_password",
    "keycloak_admin_password",
]


def step(message: str) -> None:
    print(f"{YELLOW}==>{RESET} {message}")


def detail(message: str) -> None:
    print(f"    {GREY}{message}{RESET}")


def run(args: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    """Run a command, streaming nothing, returning the result.

    Docker writes ordinary progress to stderr, so stderr is captured rather than treated as failure.
    Only the exit code decides success.
    """
    return subprocess.run(
        args, cwd=REPO, capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace",
    )


def postgres_volume_exists() -> bool:
    """True when a postgres_data volume for this compose project is already present."""
    result = run(["docker", "volume", "ls", "--format", "{{.Name}}"], timeout=60)
    if result.returncode != 0:
        return False
    return any(line.strip().endswith("postgres_data") for line in result.stdout.splitlines())


def generate_secrets() -> None:
    step("Checking local secrets")
    SECRETS_DIR.mkdir(exist_ok=True)

    created = []
    for name in SECRET_NAMES:
        path = SECRETS_DIR / name
        if path.exists() and path.read_text(encoding="utf-8").strip():
            detail(f"{name} (exists)")
            continue
        # 32 bytes of CSPRNG output, base64url. Distinct per consumer: a leak of one credential
        # must not be a leak of another. No trailing newline — containers read the file verbatim.
        value = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        path.write_text(value, encoding="utf-8", newline="")
        detail(f"{name} (generated)")
        created.append(name)

    # PostgreSQL applies POSTGRES_PASSWORD_FILE only when it initialises an empty data directory.
    # The volume outlives `docker compose down`, so a regenerated bootstrap password — a deleted
    # .secrets/, a second clone, a run that switched between sudo and not — leaves the database
    # holding the old one. Every connection then fails with "password authentication failed", and
    # nothing in the error says why. Catch it here, where it is still one command to fix.
    if "postgres_bootstrap_password" in created and postgres_volume_exists():
        print()
        print(f"{RED}The database volume already exists, but its password was just regenerated.{RESET}")
        print(f"{GREY}PostgreSQL keeps the password it was first initialised with, so the two no{RESET}")
        print(f"{GREY}longer match and the migration will fail to authenticate.{RESET}")
        print()
        print(f"{YELLOW}Rebuild the database:  python scripts/bootstrap_local.py --reset{RESET}")
        print(f"{GREY}That destroys the local database. Everything in it is seed data.{RESET}")
        print()
        raise SystemExit(1)

    env = REPO / ".env"
    if not env.exists():
        shutil.copy(REPO / ".env.example", env)
        detail(".env created from .env.example")


def ensure_tls() -> None:
    """Keycloak cannot start without its certificate.

    compose.yaml configures HTTPS unconditionally, and the certificate lives under .secrets/, which
    is not in version control. On a fresh clone the bind mount is therefore an empty directory and
    Keycloak dies with "Key material not provided to setup HTTPS" in a restart loop, taking the API
    and the approval portal with it because they wait for it to become healthy.
    """
    step("Checking Keycloak's TLS material")
    cert, key = SECRETS_DIR / "tls" / "keycloak.crt", SECRETS_DIR / "tls" / "keycloak.key"
    if cert.exists() and key.exists():
        detail("certificate already present")
        return
    result = run([sys.executable, str(REPO / "scripts" / "enable_keycloak_tls.py"),
                  "--certificate-only"], timeout=300)
    if result.returncode != 0 or not (cert.exists() and key.exists()):
        print(result.stdout[-2000:])
        print(result.stderr[-2000:])
        raise SystemExit(
            f"{RED}could not generate Keycloak's certificate{RESET}\n"
            f"{GREY}It needs the cryptography package:  pip install cryptography{RESET}"
        )
    detail("certificate generated into .secrets/tls/")


def wait_for_migration(timeout_seconds: int = 300) -> None:
    step("Waiting for the migration job")
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        result = run(
            ["docker", "inspect", "-f", "{{.State.Status}}:{{.State.ExitCode}}", "supportpilot-migrate"],
            timeout=30,
        )
        state = result.stdout.strip()
        if state == "exited:0":
            detail("migrations applied and smoke tests passed")
            return
        if state.startswith("exited:"):
            logs = run(["docker", "compose", "logs", "migrate", "--tail", "30"], timeout=60)
            print(logs.stdout[-2000:])
            raise SystemExit(f"{RED}migration job failed ({state}){RESET}")
        time.sleep(2)
    raise SystemExit(f"{RED}migration job did not finish within {timeout_seconds}s{RESET}")


def wait_for_keycloak_realm(timeout_seconds: int = 240) -> None:
    """Assert the realm is actually serving discovery over TLS.

    The container healthcheck can only confirm the port is open — the image has no HTTP client
    once TLS moves the management interface to HTTPS. This is the real check, and it is the one
    that matters: a Keycloak that is listening but has not imported the realm will fail every
    login in a way that looks like a client misconfiguration.
    """
    import json as _json
    import ssl
    import urllib.request

    step("Waiting for the Keycloak realm")
    url = "https://localhost:8443/realms/supportpilot/.well-known/openid-configuration"
    # The local certificate is self-signed; trust it explicitly rather than disabling verification.
    context = ssl.create_default_context()
    certificate = REPO / ".secrets" / "tls" / "keycloak.crt"
    if certificate.exists():
        context.load_verify_locations(cafile=str(certificate))
    else:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5, context=context) as response:
                issuer = _json.load(response)["issuer"]
                detail(f"realm serving; issuer {issuer}")
                return
        except Exception:
            time.sleep(3)
    raise SystemExit(f"{RED}Keycloak realm did not become available within {timeout_seconds}s{RESET}")


def wait_for_api(timeout_seconds: int = 240) -> None:
    step("Waiting for the API")
    # The API has no published port by design, so readiness is checked from inside the app network.
    probe = (
        "import httpx,sys\n"
        "try:\n"
        "    r = httpx.get('http://api:8000/readyz', timeout=5)\n"
        "    print(r.status_code, r.text)\n"
        "    sys.exit(0 if r.status_code == 200 else 1)\n"
        "except Exception as exc:\n"
        "    print('unreachable', exc); sys.exit(1)\n"
    )
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        result = run(
            ["docker", "compose", "exec", "-T", "approval-portal", "python", "-c", probe],
            timeout=60,
        )
        if result.returncode == 0:
            detail(result.stdout.strip())
            return
        time.sleep(4)
    logs = run(["docker", "compose", "logs", "api", "--tail", "30"], timeout=60)
    print(logs.stdout[-2000:])
    raise SystemExit(f"{RED}API did not become ready within {timeout_seconds}s{RESET}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bring up the SupportPilot local environment.")
    parser.add_argument("--rebuild", action="store_true", help="rebuild images without cache")
    parser.add_argument("--reset", action="store_true",
                        help="destroy volumes first; the database is rebuilt from migrations")
    args = parser.parse_args()

    if shutil.which("docker") is None:
        raise SystemExit(f"{RED}docker is not on PATH{RESET}")

    generate_secrets()
    ensure_tls()

    if args.reset:
        step("Removing containers and volumes")
        run(["docker", "compose", "down", "-v"], timeout=300)

    if args.rebuild:
        step("Rebuilding images without cache")
        result = run(["docker", "compose", "build", "--no-cache"])
        if result.returncode != 0:
            print(result.stdout[-3000:], result.stderr[-3000:])
            raise SystemExit(f"{RED}image build failed{RESET}")

    step("Starting services")
    result = run(["docker", "compose", "up", "-d", "--build"])
    if result.returncode != 0:
        print(result.stdout[-3000:])
        print(result.stderr[-3000:])
        # "service migrate didn't complete successfully: exit 2" says nothing about the cause, and
        # the container that holds the reason has already exited. Fetch it rather than making the
        # reader go looking.
        combined = result.stdout + result.stderr
        if "migrate" in combined:
            logs = run(["docker", "compose", "logs", "--no-color", "--tail", "40", "migrate"])
            print()
            print(f"{YELLOW}migrate said:{RESET}")
            print(logs.stdout[-3000:])
            if "password authentication failed" in logs.stdout:
                print(f"{RED}The database is holding a different password than .secrets/ has.{RESET}")
                print(f"{GREY}PostgreSQL keeps the password its data directory was created with,{RESET}")
                print(f"{GREY}and that volume survives `docker compose down`.{RESET}")
                print()
                print(f"{YELLOW}Rebuild it:  python scripts/bootstrap_local.py --reset{RESET}")
                print(f"{GREY}That destroys the local database. Everything in it is seed data.{RESET}")
        raise SystemExit(f"{RED}docker compose up failed{RESET}")
    detail("containers started")

    wait_for_migration()
    wait_for_keycloak_realm()
    wait_for_api()

    print()
    print(f"{GREEN}Environment is up.{RESET}")
    print("  Keycloak         https://localhost:8443  (realm: supportpilot)")
    print(f"  {GREY}                 http://localhost:8080 also served, for the test harness{RESET}")
    print("  Approval portal  http://localhost:8090")
    print(f"  API              {GREY}internal only — reachable from the app network, by design{RESET}")
    print()
    print(f"{GREY}Onyx is not started here. It ships as its own compose project;{RESET}")
    print(f"{GREY}see LAB.md part B if you want a model in the loop.{RESET}")
    print()
    print(f"{YELLOW}Next: python scripts/verify_local.py{RESET}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
