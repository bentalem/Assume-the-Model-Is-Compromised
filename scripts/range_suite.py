"""The Range's own test suite.

Five things, and each one corresponds to a specific way this service could leave a learner worse
off than not having used it:

    round trip        an arm whose restore does not work — the failure that leaves a lab quietly
                      wrong for the rest of the afternoon
    probe honesty     a console that reports `correct` for a system that is armed
    reset             a reset that reports success without restoring
    flag integrity    a challenge solvable by pressing a button before touching anything
    declared surface  a control on a page that is not in the registry, or the reverse

It drives the service over HTTP, the way a learner does, rather than calling the registry in
process. A registry that works and a console that cannot reach it is still a broken product.

    python scripts/range_suite.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8095"

GREEN, RED, YELLOW, GREY, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[1m", "\033[0m"
)

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    if ok:
        print(f"  {GREEN}ok{RESET}   {name}{('  ' + GREY + detail + RESET) if detail else ''}")
    else:
        failures.append(name)
        print(f"  {RED}FAIL{RESET} {name}{('  — ' + detail) if detail else ''}")
    return ok


def get(path: str) -> str:
    with urllib.request.urlopen(BASE + path, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def post(path: str, fields: dict[str, str]) -> str:
    data = urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(BASE + path, data=data, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.read().decode("utf-8", "replace")


def probe_of(page: str, mutation_id: str) -> str:
    """Read one control's state out of the rendered page — what the learner actually sees."""
    marker = f"{mutation_id} · "
    index = page.find(marker)
    if index < 0:
        return "absent"
    return page[index + len(marker):].split("<")[0].strip()


def _owner_of(mutation_id: str) -> str | None:
    """Find a challenge whose console declares this mutation.

    The console deliberately refuses a mutation a challenge does not declare, so a sweep over
    the whole registry has to arm each one through a page that owns it.
    """
    for fragment in get("/").split('href="/c/')[1:]:
        challenge_id = fragment.split('"')[0]
        # The same marker probe_of uses, so "declared on this page" means exactly what it means
        # there — and an id that is a prefix of another cannot match the wrong one.
        if f"{mutation_id} · " in get(f"/c/{challenge_id}"):
            return challenge_id
    return None


def sql(statement: str) -> str:
    """Read the database directly, to check the console against the system it claims to describe."""
    password = (REPO / ".secrets" / "postgres_bootstrap_password").read_text(encoding="utf-8").strip()
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "-e", f"PGPASSWORD={password}", "postgres",
         "psql", "-U", "supportpilot_admin", "-d", "supportpilot", "-tAX", "-c", statement],
        cwd=REPO, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace",
    )
    return proc.stdout.strip()


def main() -> int:
    print()
    print(f"{BOLD}The Range{RESET}")
    print("=" * 74)

    try:
        health = json.loads(get("/healthz"))
    except Exception as exc:  # noqa: BLE001
        print(f"\n  {RED}The Range is not reachable at {BASE}: {exc}{RESET}")
        print(f"  {GREY}docker compose --profile range up -d range{RESET}\n")
        return 1

    check("service healthy", health.get("status") == "ok", health.get("database", ""))
    check("content loaded", health.get("challenges", 0) > 0, f"{health.get('challenges')} challenge(s)")
    check("environment is local", health.get("environment") == "local")

    challenge_id = "2.1-policy-that-filters-nothing"
    mutations = ["rls.orders.force_off", "rls.orders.disable"]

    # Every registered mutation, not a hardcoded pair.
    #
    # "No mutation without a proven inverse" is a hard requirement, and a suite that round-trips two
    # ids by name leaves every mutation added afterwards untested by default - the opposite of what
    # that rule asks for. The service lists its own vocabulary at /registry and this reads it, so a
    # new mutation is covered the moment it is registered rather than when somebody remembers it.
    try:
        listing = json.loads(get("/registry"))
        all_mutations = [m["id"] for m in listing["mutations"]]
    except Exception as exc:  # noqa: BLE001
        all_mutations = []
        check("the service lists its registry", False, str(exc))
    else:
        check("the service lists its registry", bool(all_mutations),
              f"{len(all_mutations)} mutation(s)")

    # ---------------------------------------------------------------------------------------------
    print(f"\n  {GREY}starting from a known-good environment{RESET}")
    post(f"/c/{challenge_id}/reset", {})
    page = get(f"/c/{challenge_id}")
    for mutation in mutations:
        check(f"{mutation} starts correct", probe_of(page, mutation) == "correct")

    # ---------------------------------------------------------------------------------------------
    print(f"\n  {GREY}flag integrity — the property that makes the challenge worth doing{RESET}")
    unarmed = post(f"/c/{challenge_id}/flag", {"answer": "512.00"})
    check(
        "the flag is unobtainable while every control holds",
        "Not a value" in unarmed,
        "a flag readable unarmed can be guessed rather than earned",
    )

    # ---------------------------------------------------------------------------------------------
    print(f"\n  {GREY}round trip, per mutation{RESET}")
    for mutation in mutations:
        armed_page = post(f"/c/{challenge_id}/arm", {"mutation": mutation})
        armed_probe = probe_of(armed_page, mutation)
        check(f"{mutation}: arms", armed_probe == "armed", f"probe says {armed_probe!r}")

        # Probe honesty: the page must agree with the catalogue, not with what the service believes.
        catalogue = sql(
            "SELECT relrowsecurity::text || '/' || relforcerowsecurity::text FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname='app' AND c.relname='orders'"
        )
        # Exact, not a prefix. Disabling row security leaves relforcerowsecurity set, so the armed
        # state is `false/true` — and a test that matched only `false` would pass for a state it
        # never checked, which is the kind of lie CLAUDE.md names.
        expected = {
            "rls.orders.force_off": "true/false",
            "rls.orders.disable": "false/true",
        }[mutation]
        check(
            f"{mutation}: the console agrees with the database",
            catalogue == expected,
            f"catalogue says {catalogue!r}, expected {expected!r}",
        )

        restored_page = post(f"/c/{challenge_id}/restore", {"mutation": mutation})
        restored_probe = probe_of(restored_page, mutation)
        check(f"{mutation}: restores", restored_probe == "correct", f"probe says {restored_probe!r}")

    # ---------------------------------------------------------------------------------------------
    print(f"\n  {GREY}the flag, once the control is actually broken{RESET}")
    post(f"/c/{challenge_id}/arm", {"mutation": "rls.orders.force_off"})
    armed = post(f"/c/{challenge_id}/flag", {"answer": "512.00"})
    check("the flag is obtainable once armed", "Correct" in armed)

    observed = post(f"/c/{challenge_id}/observe", {"observation": "orders.as_owner"})
    check(
        "the observation shows the foreign tenant's row",
        "22222222-2222-2222-2222-222222222222" in observed,
    )

    # ---------------------------------------------------------------------------------------------
    print(f"\n  {GREY}reset from an arbitrary armed set{RESET}")
    post(f"/c/{challenge_id}/arm", {"mutation": "rls.orders.disable"})
    reset_page = post(f"/c/{challenge_id}/reset", {})
    check("reset names what it changed", "restored:" in reset_page)

    after = get(f"/c/{challenge_id}")
    for mutation in mutations:
        check(f"{mutation}: correct after reset", probe_of(after, mutation) == "correct")

    catalogue = sql(
        "SELECT relrowsecurity::text || '/' || relforcerowsecurity::text FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname='app' AND c.relname='orders'"
    )
    check("the database really is restored", catalogue == "true/true", f"catalogue says {catalogue!r}")

    post(f"/c/{challenge_id}/flag", {"answer": "512.00"})
    final = post(f"/c/{challenge_id}/flag", {"answer": "512.00"})
    check("the flag is unobtainable again after reset", "Not a value" in final)

    # ---------------------------------------------------------------------------------------------
    print(f"\n  {GREY}round trip, every other registered mutation{RESET}")
    for mutation in [m for m in all_mutations if m not in mutations]:
        owner = _owner_of(mutation)
        if owner is None:
            # Registered authority no console can reach or restore from. Nothing is broken by
            # it today, and it is still a defect: reset can restore it, a learner cannot.
            check(f"{mutation}: some challenge declares it", False,
                  "not reachable from any console")
            continue

        armed = probe_of(post(f"/c/{owner}/arm", {"mutation": mutation}), mutation)
        check(f"{mutation}: arms", armed == "armed", f"probe says {armed!r}")

        restored = probe_of(post(f"/c/{owner}/restore", {"mutation": mutation}), mutation)
        check(f"{mutation}: restores", restored == "correct", f"probe says {restored!r}")

    print(f"\n  {GREY}the declared surface{RESET}")
    refused = post(f"/c/{challenge_id}/arm", {"mutation": "rls.customers.force_off"})
    check(
        "a mutation this challenge does not declare is refused",
        "not a control of this challenge" in refused,
    )
    refused = post(f"/c/{challenge_id}/observe", {"observation": "../../etc/passwd"})
    check("an unregistered observation is refused", "not an observation" in refused)

    # ---------------------------------------------------------------------------------------------
    print(f"\n  {GREY}evidence{RESET}")
    rows = sql("SELECT count(*) FROM app.audit_events WHERE actor_type = 'range'")
    check("the Range's own actions are in the lab's audit trail", int(rows or 0) > 0, f"{rows} row(s)")

    # ---------------------------------------------------------------------------------------------
    # The last thing, and the one that matters most: what state is the lab actually in now?
    #
    # Everything above tested reset by calling it and reading the console back. This asks the
    # database directly, after the suite has finished, because a suite that leaves the lab armed
    # while reporting success is the exact failure this file exists to prevent — and it is also the
    # failure that is easiest to write by accident.
    # ---------------------------------------------------------------------------------------------
    print(f"\n  {GREY}the state this suite leaves behind{RESET}")
    unprotected = sql(
        "SELECT coalesce(string_agg(relname, ', '), 'none') FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'app' AND c.relkind = 'r' AND c.relname <> 'schema_migrations' "
        "AND NOT (c.relrowsecurity AND c.relforcerowsecurity)"
    )
    check(
        "every table in app is enabled and forced when the suite exits",
        unprotected == "none",
        f"still unprotected: {unprotected}",
    )

    print()
    if failures:
        print(f"  {RED}{len(failures)} check(s) failed{RESET}")
        print(f"  {YELLOW}A failing round trip means a learner's lab can be left broken.{RESET}\n")
        return 1
    print(f"  {GREEN}all checks passed{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
