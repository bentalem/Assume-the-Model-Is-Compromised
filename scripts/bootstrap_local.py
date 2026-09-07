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


def generate_secrets() -> None:
    step("Checking local secrets")
    SECRETS_DIR.mkdir(exist_ok=True)

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

    env = REPO / ".env"
    if not env.exists():
        shutil.copy(REPO / ".env.example", env)
        detail(".env created from .env.example")


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
    parser.add_argument("--with-onyx", action="store_true", help="also start Onyx (ADR-0002)")
    parser.add_argument("--rebuild", action="store_true", help="rebuild images without cache")
    parser.add_argument("--reset", action="store_true",
                        help="destroy volumes first; the database is rebuilt from migrations")
    args = parser.parse_args()

    if shutil.which("docker") is None:
        raise SystemExit(f"{RED}docker is not on PATH{RESET}")

    generate_secrets()

    profile = ["--profile", "onyx"] if args.with_onyx else []

    if args.reset:
        step("Removing containers and volumes")
        run(["docker", "compose", *profile, "down", "-v"], timeout=300)

    if args.rebuild:
        step("Rebuilding images without cache")
        result = run(["docker", "compose", *profile, "build", "--no-cache"])
        if result.returncode != 0:
            print(result.stdout[-3000:], result.stderr[-3000:])
            raise SystemExit(f"{RED}image build failed{RESET}")

    step("Starting services")
    result = run(["docker", "compose", *profile, "up", "-d", "--build"])
    if result.returncode != 0:
        print(result.stdout[-3000:])
        print(result.stderr[-3000:])
        raise SystemExit(f"{RED}docker compose up failed{RESET}")
    detail("containers started")

    wait_for_migration()
    wait_for_api()

    print()
    print(f"{GREEN}Environment is up.{RESET}")
    print("  Keycloak         http://localhost:8080   (realm: supportpilot)")
    print("  Approval portal  http://localhost:8090")
    print(f"  API              {GREY}internal only — reachable from the app network, by design{RESET}")
    if args.with_onyx:
        print("  Onyx             http://localhost:3000")
    print()
    print(f"{YELLOW}Next: python scripts/verify_local.py{RESET}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
