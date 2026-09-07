"""Secret scan (P0-11).

Runs as a pre-commit hook and in the pipeline. Blocks a commit that would put a credential into the
repository — the rule the baseline states as "secrets are absent from source, images, prompts, and
logs" (SP-BUILD-001 section 12).

Two things are checked:

  1. No file under .secrets/ is staged. Those files hold real generated credentials.
  2. No staged file contains something that looks like a credential.

Known-safe fixtures are allowed by exact path: the local Keycloak realm's test passwords are in the
same class as the seeded orders — throwaway values for a throwaway realm — and are marked as such.

Run: python scripts/scan_secrets.py            scan staged files (hook mode)
     python scripts/scan_secrets.py --all      scan every tracked file
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

RED, GREEN, YELLOW, GREY, RESET = "\033[31m", "\033[32m", "\033[33m", "\033[90m", "\033[0m"

# Paths whose credential-shaped strings are deliberate local fixtures, not secrets.
ALLOWED_PATHS = {
    "infrastructure/local/keycloak/supportpilot-realm.json",  # local realm test users
    "scripts/scan_secrets.py",                                 # this file's own patterns
    "scripts/verify_local.py",                                 # references fixture passwords
    "docs/08-local-build-runbook.md",                          # documents the fixtures
    # The redaction tests must contain realistic secret shapes — that is what they assert gets
    # redacted. Every value there is fabricated and matched only against the redactor's output.
    "services/api/tests/test_observability.py",
    "docs/runbooks/incidents.md",                               # shows the rotation commands
}

BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".docx", ".xlsx", ".whl", ".zip", ".ico"}

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b")),
    ("Anthropic-style key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("postgres URI with password", re.compile(r"postgres(?:ql)?://[^\s:@/]+:[^\s@/]+@")),
    (
        "assigned credential",
        # KEY = "value" where the key looks like a credential and the value is not obviously a
        # placeholder or a file reference.
        #
        # No \b anchors: underscore is a word character, so \bpassword\b never matches inside
        # DB_PASSWORD — which is exactly how these are usually named. Surrounding word characters
        # are allowed instead.
        re.compile(
            r"(?i)[a-z0-9_.-]*"
            r"(?:password|passwd|secret|api[_-]?key|access[_-]?token|private[_-]?key|credential)"
            r"[a-z0-9_.-]*\s*[:=]\s*[\"']([^\"'\n]{8,})[\"']"
        ),
    ),
]

# Values that match a pattern but are plainly not credentials.
PLACEHOLDER = re.compile(
    r"(?i)^(?:"
    r"\$\{.*\}|<.*>|\{\{.*\}\}|"                     # substitutions
    r"\$+\(.*\)|\$+[a-z_][a-z0-9_]*|"                # shell command substitution and var refs
    r":'[a-z_]+'|:[a-z_]+|%[sL]|\$[0-9]+|"           # psql / SQL bind placeholders
    r"[a-z][a-z_]*|"                                 # a bare lowercase identifier: a variable
                                                     # name such as migrator_password, not a
                                                     # value. Real credentials are not pure
                                                     # lowercase words — the trade-off is that a
                                                     # deliberately weak all-lowercase password
                                                     # would pass, which entropy checks in the
                                                     # pipeline (P5-10) are meant to catch.
    r".*_FILE$|/run/secrets/.*|.*\.secrets/.*|"      # file references
    r"(?:x{3,}|\*{3,}|\.{3,})|"                      # masked
    r"(?:changeme|example|placeholder|redacted|dummy|sample|test|none|null|true|false)"
    r"[a-z0-9_-]*|"
    r".*-local-password|"                            # local realm fixtures
    r".*(?:password|secret|key)_file.*"
    r")$"
)


def is_placeholder(value: str) -> bool:
    """True when a captured value is plainly not a credential.

    The regex handles the common placeholder shapes. This function also catches shell interpolation,
    which the capture group mangles: in

        BOOTSTRAP_PASSWORD="$(read_secret "$BOOTSTRAP_PASSWORD_FILE")"

    the inner quote ends the capture early, leaving "$(read_secret " — a fragment no closing-paren
    pattern can match. Any value containing an interpolation is a reference, not a secret.
    """
    value = value.strip()
    if not value:
        return True
    if value.startswith("$") or "$(" in value or "${" in value:
        return True
    if value.startswith("/run/secrets/") or value.endswith("_FILE"):
        return True
    return bool(PLACEHOLDER.match(value))


def staged_files() -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        cwd=REPO, capture_output=True, text=True,
    )
    return [f for f in proc.stdout.splitlines() if f.strip()]


def tracked_files() -> list[str]:
    proc = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True)
    return [f for f in proc.stdout.splitlines() if f.strip()]


def scan(paths: list[str]) -> list[str]:
    findings: list[str] = []

    for relative in paths:
        # 1. A secret file must never be staged, whatever it contains.
        if relative.startswith(".secrets/") and not relative.endswith(".gitkeep"):
            findings.append(f"{relative}: file from .secrets/ is staged")
            continue

        if relative in ALLOWED_PATHS:
            continue

        path = REPO / relative
        if not path.is_file() or path.suffix.lower() in BINARY_SUFFIXES:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in PATTERNS:
                match = pattern.search(line)
                if not match:
                    continue
                value = match.group(1) if match.groups() else match.group(0)
                if is_placeholder(value):
                    continue
                excerpt = line.strip()[:100]
                findings.append(f"{relative}:{line_number}: {label} — {excerpt}")

    return findings


def main() -> int:
    scan_all = "--all" in sys.argv
    paths = tracked_files() if scan_all else staged_files()

    if not paths:
        print(f"{GREY}secret scan: nothing to scan{RESET}")
        return 0

    findings = scan(paths)

    if findings:
        print(f"{RED}Secret scan failed — commit blocked.{RESET}\n")
        for finding in findings:
            print(f"  {finding}")
        print(
            f"\n{YELLOW}Credentials belong in ./.secrets/ (generated locally, never committed) or in\n"
            f"the production secret manager. If this is a deliberate fixture, add its exact path to\n"
            f"ALLOWED_PATHS in scripts/scan_secrets.py and say why in the commit.{RESET}\n"
        )
        return 1

    print(f"{GREEN}secret scan: clean{RESET} {GREY}({len(paths)} file(s)){RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
