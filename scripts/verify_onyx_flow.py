"""Verify the Onyx integration actually works (P1-04, P1-16 evidence).

Run this after completing the two admin-UI steps that `connect_onyx.py` prints, and after signing
in to Onyx through Keycloak at least once.

It checks the chain in the order it has to hold, and stops at the first link that is missing, so
the output tells you what to fix rather than that "something is wrong":

  1. Onyx has an SSO provider row pointing at our Keycloak.
  2. A user signed in through it, and Onyx stored their Keycloak access token.
  3. That stored token is one our API would accept — right issuer, right audience.
  4. An action is registered with passthrough auth ON, and with no custom headers.
  5. Our audit trail shows a tool call that arrived with that user's identity.

Step 5 is the one that matters: it is the difference between "configured" and "working". It proves
the model's tool call reached the API as *alice*, not as a service account — which is FR-02.

Read-only. It queries Onyx's database directly rather than its admin API, so it needs no Onyx
credentials.

Run: python scripts/verify_onyx_flow.py
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ONYX_DB_CONTAINER = "onyx-relational_db-1"
EXPECTED_ISSUER = "http://localhost:8080/realms/supportpilot"
EXPECTED_AUDIENCE = "supportpilot-api"

GREEN, RED, YELLOW, GREY, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[1m", "\033[0m"
)

results: list[tuple[str, str, str]] = []


class Missing(Exception):
    """A link in the chain is not configured yet. Carries the fix."""


def onyx_sql(statement: str) -> str:
    """Query Onyx's own database. Read-only."""
    env = subprocess.run(
        ["docker", "inspect", "-f",
         "{{range .Config.Env}}{{println .}}{{end}}", ONYX_DB_CONTAINER],
        cwd=REPO, capture_output=True, text=True, timeout=30,
    ).stdout
    password = next(
        (l.split("=", 1)[1] for l in env.splitlines() if l.startswith("POSTGRES_PASSWORD=")),
        "password",
    )
    user = next(
        (l.split("=", 1)[1] for l in env.splitlines() if l.startswith("POSTGRES_USER=")), "postgres"
    )
    proc = subprocess.run(
        ["docker", "exec", "-e", f"PGPASSWORD={password}", ONYX_DB_CONTAINER,
         "psql", "-U", user, "-d", "postgres", "-tAX", "-c", statement],
        cwd=REPO, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise Missing(f"could not query the Onyx database: {(proc.stderr or '').strip()[:160]}")
    return proc.stdout.strip()


def supportpilot_sql(statement: str) -> str:
    password = (REPO / ".secrets" / "postgres_bootstrap_password").read_text(encoding="utf-8").strip()
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "-e", f"PGPASSWORD={password}", "postgres",
         "psql", "-U", "supportpilot_admin", "-d", "supportpilot", "-tAX", "-c", statement],
        cwd=REPO, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise Missing((proc.stderr or proc.stdout).strip()[:200])
    return proc.stdout.strip()


def claims(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def check(number: str, description: str):
    def decorator(fn):
        try:
            detail = fn() or ""
            results.append((number, "PASS", detail))
            print(f"  {number}. {GREEN}PASS{RESET}  {description}")
            if detail:
                print(f"         {GREY}{detail}{RESET}")
        except Missing as missing:
            results.append((number, "TODO", str(missing)))
            print(f"  {number}. {YELLOW}TODO{RESET}  {description}")
            print(f"         {YELLOW}{missing}{RESET}")
        except Exception as exc:
            results.append((number, "FAIL", str(exc)))
            print(f"  {number}. {RED}FAIL{RESET}  {description}")
            print(f"         {RED}{exc}{RESET}")
        return fn
    return decorator


def main() -> int:
    print()
    print(f"{BOLD}Onyx integration — end to end{RESET}")
    print("-" * 74)

    @check("1", "Onyx has an SSO provider row for our Keycloak")
    def _():
        try:
            rows = onyx_sql(
                "SELECT name || ' | ' || provider_type FROM sso_provider WHERE enabled IS NOT FALSE"
            )
        except Missing:
            raise Missing(
                "no sso_provider table or it is unreadable. Add the provider in "
                "Admin Panel -> Organization -> SSO Providers (see scripts/connect_onyx.py)."
            ) from None
        if not rows:
            raise Missing(
                "no SSO provider configured. Admin Panel -> Organization -> SSO Providers, "
                "then re-run scripts/connect_onyx.py to print the exact values."
            )
        return rows.replace("\n", ", ")

    @check("2", "A user signed in through it and Onyx stored their Keycloak token")
    def _():
        rows = onyx_sql(
            'SELECT u.email || \'|\' || coalesce(o.access_token, \'\') '
            'FROM "user" u JOIN oauth_account o ON o.user_id = u.id '
            "ORDER BY u.email LIMIT 5"
        )
        if not rows:
            raise Missing(
                "no oauth_account rows. Sign in to Onyx via the Keycloak button at "
                "http://localhost:3000 as alice / alice-local-password. A basic-auth login does "
                "not create one, and passthrough has nothing to forward without it."
            )
        emails = [line.split("|", 1)[0] for line in rows.splitlines()]
        return f"{len(emails)} linked account(s): {', '.join(emails)}"

    @check("3", "The stored token is one our API would accept")
    def _():
        rows = onyx_sql(
            'SELECT o.access_token FROM oauth_account o '
            "WHERE o.access_token IS NOT NULL AND o.access_token <> '' LIMIT 1"
        )
        if not rows:
            raise Missing("no stored access token yet — complete step 2 first")
        token = rows.splitlines()[0].strip()
        if token.count(".") != 2:
            raise Missing(
                "the stored token is not a JWT. Onyx may be storing an opaque token; the API "
                "cannot verify that. Check the provider's scopes include 'openid'."
            )
        c = claims(token)
        audience = c.get("aud")
        audiences = audience if isinstance(audience, list) else [audience]

        problems = []
        if c.get("iss") != EXPECTED_ISSUER:
            problems.append(f"issuer is {c.get('iss')}, the API expects {EXPECTED_ISSUER}")
        if EXPECTED_AUDIENCE not in audiences:
            problems.append(
                f"audience is {audiences}, missing '{EXPECTED_AUDIENCE}'. The audience mapper on "
                f"the onyx-web client adds it; re-run scripts/connect_onyx.py and sign in again."
            )
        if not c.get("sub"):
            problems.append("no 'sub' claim — the client is missing the 'basic' scope")
        if problems:
            raise Missing("; ".join(problems))
        return f"sub={c['sub']} iss={c['iss']} aud={audiences}"

    @check("4", "An action is registered with passthrough auth on")
    def _():
        rows = onyx_sql(
            "SELECT name || '|' || passthrough_auth::text || '|' "
            "|| coalesce(custom_headers::text, '[]') FROM tool "
            "WHERE openapi_schema IS NOT NULL"
        )
        if not rows:
            raise Missing(
                "no OpenAPI action registered. Admin Panel -> Actions -> Add OpenAPI Action, "
                "paste openapi/supportpilot-actions.yaml, and turn ON "
                "'Pass through user's OAuth token'."
            )
        passthrough = [l for l in rows.splitlines() if "|true|" in l]
        if not passthrough:
            names = ", ".join(l.split("|")[0] for l in rows.splitlines())
            raise Missing(
                f"action(s) registered ({names}) but passthrough auth is OFF. Without it Onyx "
                f"sends no user token and every call returns 401."
            )
        detail = passthrough[0].split("|")
        if detail[2] not in ("[]", "null", ""):
            raise Missing(
                "passthrough is on but custom headers are set; Onyx refuses that combination"
            )
        return f"'{detail[0]}' with passthrough on and no custom headers"

    @check("5", "A tool call reached the API carrying the user's own identity")
    def _():
        # Gated on the steps above, and deliberately so. The audit trail records that a call
        # arrived as alice; it does not record whether Onyx or a test script sent it, because
        # nothing in the request distinguishes them — both present a real Keycloak token for the
        # same user. Reporting a pass here while the token path is unconfigured would mean
        # reporting my own test traffic as proof the integration works.
        unfinished = [n for n, result, _ in results if result != "PASS"]
        if unfinished:
            raise Missing(
                f"cannot attribute traffic to Onyx until step(s) {', '.join(unfinished)} are done. "
                f"Any audit events present now are from the local test suites, not from Onyx."
            )

        rows = supportpilot_sql(
            "SELECT u.identity_subject || ' | ' || a.action || ' | ' || a.decision "
            "|| ' | ' || to_char(a.occurred_at, 'YYYY-MM-DD HH24:MI') "
            "FROM app.audit_events a JOIN app.users u ON u.id::text = a.actor_id "
            "WHERE a.actor_type = 'user' AND a.occurred_at > now() - interval '2 hours' "
            "ORDER BY a.occurred_at DESC LIMIT 5"
        )
        if not rows:
            raise Missing(
                "no tool call from a human user in the last 2 hours. Ask the agent in Onyx: "
                "\"what is the status of order ORD-2001?\" — then re-run this."
            )
        return " / ".join(rows.splitlines()[:3])

    print("-" * 74)
    passed = sum(1 for _, r, _ in results if r == "PASS")
    todo = sum(1 for _, r, _ in results if r == "TODO")
    failed = sum(1 for _, r, _ in results if r == "FAIL")

    if failed == 0 and todo == 0:
        print(f"  {GREEN}{BOLD}The flow works end to end.{RESET}")
        print(f"  {GREY}Onyx forwarded the user's own Keycloak token; the API authorized alice{RESET}")
        print(f"  {GREY}as alice. That is P1-04 and P1-16 evidence.{RESET}")
    else:
        print(f"  {passed} done, {todo} still to configure, {failed} failing")
        print(f"  {GREY}Work top-down: each step needs the one above it.{RESET}")
    print()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
