"""Confirm every dependency is pinned and vendored (P0-04, P5-11).

Images install with the package index disabled, so a requirement without a matching wheel in
vendor/ does not fail at review time — it fails at build time, usually on someone else's machine.
This turns that into a fast, local check.

It asserts three things:

  1. every requirement is pinned to an exact version (== , never >= or a bare name);
  2. a wheel for that exact version exists in vendor/wheels;
  3. no two wheels supply different versions of the same distribution, which would make the
     installed set depend on resolution order rather than on the pins.

Run: python scripts/check_vendored_wheels.py
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WHEELS = REPO / "vendor" / "wheels"
REQUIREMENTS = sorted(REPO.glob("services/*/requirements.txt"))

GREEN, RED, GREY, RESET = "\033[32m", "\033[31m", "\033[90m", "\033[0m"

# name==version, optionally with extras: psycopg[binary,pool]==3.2.3
_REQUIREMENT = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)(?:\[[^\]]+\])?==(?P<version>[A-Za-z0-9._-]+)$")


def normalise(name: str) -> str:
    """PEP 503 normalisation: pypi-name and pypi_name are the same distribution."""
    return re.sub(r"[-_.]+", "-", name).lower()


def vendored() -> dict[str, set[str]]:
    found: dict[str, set[str]] = defaultdict(set)
    for wheel in WHEELS.glob("*.whl"):
        parts = wheel.name.split("-")
        if len(parts) < 2:
            continue
        found[normalise(parts[0])].add(parts[1])
    return found


def main() -> int:
    if not WHEELS.is_dir():
        print(f"{RED}vendor/wheels does not exist{RESET}")
        return 1

    available = vendored()
    problems: list[str] = []
    checked = 0

    for requirements_file in REQUIREMENTS:
        service = requirements_file.parent.name
        for number, raw in enumerate(requirements_file.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue

            match = _REQUIREMENT.match(line)
            if not match:
                problems.append(
                    f"{service}/requirements.txt:{number}: '{line}' is not pinned with == "
                    f"(an unpinned dependency cannot be vendored reproducibly)"
                )
                continue

            checked += 1
            name = normalise(match["name"])
            version = match["version"]
            if name not in available:
                problems.append(
                    f"{service}: no wheel vendored for {match['name']} "
                    f"(run: pip download --platform manylinux2014_x86_64 --python-version 312 "
                    f"--only-binary=:all: -d vendor/wheels {line})"
                )
            elif version not in available[name]:
                have = ", ".join(sorted(available[name]))
                problems.append(
                    f"{service}: {match['name']} is pinned to {version} but vendor/wheels has {have}"
                )

    # A second version of the same distribution makes the install order-dependent.
    for name, versions in sorted(available.items()):
        if len(versions) > 1:
            problems.append(
                f"vendor/wheels holds {len(versions)} versions of {name} ({', '.join(sorted(versions))}); "
                f"remove the ones no requirements file pins"
            )

    if problems:
        print(f"{RED}Vendored dependency check failed:{RESET}\n")
        for problem in problems:
            print(f"  - {problem}")
        print()
        return 1

    print(f"{GREEN}All {checked} pinned requirement(s) have a matching vendored wheel{RESET}")
    print(f"{GREY}{len(available)} distribution(s) in vendor/wheels{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
