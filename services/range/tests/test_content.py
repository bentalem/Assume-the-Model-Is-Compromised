"""Content and rendering checks for the Range.

These run without a database and without the stack up. They are the tests a content author breaks:
a malformed manifest, a tab that lost its heading, a flag that cannot be checked, a hint that grew
into a fourth.

    python services/range/tests/test_content.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from range_service import render  # noqa: E402
from range_service.content import ContentError, load_all, load_challenge  # noqa: E402
from range_service.main import EnvironmentRefused, assert_local  # noqa: E402

CONTENT = ROOT / "content"

GREEN, RED, GREY, BOLD, RESET = "\033[32m", "\033[31m", "\033[90m", "\033[1m", "\033[0m"

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  {GREEN}ok{RESET}   {name}")
    else:
        failures.append(name)
        print(f"  {RED}FAIL{RESET} {name}{'  — ' + detail if detail else ''}")


def main() -> int:
    print()
    print(f"{BOLD}Range content{RESET}")
    print("-" * 74)

    challenges = load_all(CONTENT)
    check("at least one challenge loads", bool(challenges))
    if not challenges:
        return 1

    for challenge in challenges:
        print(f"\n  {GREY}{challenge.number} {challenge.title}{RESET}")

        check(f"{challenge.number}: stage 01 has tabs", bool(challenge.stage_01))
        check(f"{challenge.number}: has an objective", len(challenge.objective) > 20)
        check(f"{challenge.number}: at most three hints", len(challenge.hints) <= 3)

        # A hint that states the answer is a content bug. This cannot be checked mechanically, but a
        # hint that is not a question is the cheap half of it.
        #
        # The failure message names the offender. Without it the check reports "every hint is a
        # question: FAIL" and leaves an author re-reading three hints to find which — which is how
        # this one got committed twice while its output scrolled past.
        offenders = [h for h in challenge.hints if not h.strip().endswith("?")]
        check(
            f"{challenge.number}: every hint is a question",
            not offenders,
            f"not a question: {offenders[0][:70]}…" if offenders else "",
        )

        # Source references must resolve against the repository, or Stage 03 points at nothing.
        # This is the mechanism that stops the material drifting away from the lab.
        for ref in challenge.sources:
            path = ROOT.parent.parent / ref.path
            exists = path.is_file()
            check(f"{challenge.number}: source exists — {ref.path}", exists)
            if not exists:
                continue
            total = len(path.read_text(encoding="utf-8").splitlines())
            check(
                f"{challenge.number}: line range within {ref.path} (1–{total})",
                1 <= ref.lines[0] <= ref.lines[1] <= total,
                f"declared {ref.lines[0]}–{ref.lines[1]}",
            )
            if ref.highlight:
                check(
                    f"{challenge.number}: highlight inside its range — {ref.path}",
                    ref.lines[0] <= ref.highlight[0] <= ref.highlight[1] <= ref.lines[1],
                )

        page = render.challenge_page(challenge)
        check(f"{challenge.number}: all three stages render", all(
            marker in page for marker in ('id="stage-01"', 'id="stage-02"', 'id="stage-03"')
        ))
        check(
            f"{challenge.number}: every control renders its registry id",
            all(control.mutation in page for control in challenge.controls),
        )
        check(
            f"{challenge.number}: no unrendered markdown emphasis",
            "**" not in page,
        )
        check(
            f"{challenge.number}: skip-test framing appears once",
            page.count("Skip this stage only if") <= 1,
        )

    print(f"\n  {GREY}service guards{RESET}")

    # The refusal to run outside a local lab is the largest single guard on this service, so it is
    # tested rather than trusted.
    try:
        assert_local("production")
        check("refuses to start outside local", False, "it accepted 'production'")
    except EnvironmentRefused:
        check("refuses to start outside local", True)

    try:
        assert_local("")
        check("refuses to start with no environment set", False, "it accepted ''")
    except EnvironmentRefused:
        check("refuses to start with no environment set", True)

    check("accepts local", assert_local("local") == "local")

    # An unloadable challenge must be skipped, not crash the service.
    try:
        load_challenge(CONTENT)  # the content root itself has no manifest
        check("a directory with no manifest raises ContentError", False)
    except ContentError:
        check("a directory with no manifest raises ContentError", True)

    print()
    if failures:
        print(f"  {RED}{len(failures)} check(s) failed{RESET}\n")
        return 1
    print(f"  {GREEN}all checks passed{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
