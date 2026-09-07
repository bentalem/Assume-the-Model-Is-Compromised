"""Build a CA bundle that trusts the public roots *and* the local Keycloak certificate.

`SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` replace the trust store; they do not add to it. Pointing
them at a single self-signed certificate makes a container trust exactly that one certificate and
nothing else — so Keycloak verifies and every public HTTPS call fails with

    [SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate

which is what happened to Onyx's model provider calls after the TLS work.

A trust store is a list, so the fix is to concatenate: the public roots first, then the local
certificate. Nothing is weakened — the public roots are unchanged and one extra CA is added, scoped
to a file only these containers mount.

Run: python scripts/build_ca_bundle.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TLS_DIR = REPO / ".secrets" / "tls"
KEYCLOAK_CERT = TLS_DIR / "keycloak.crt"
BUNDLE = TLS_DIR / "ca-bundle.crt"

GREEN, RED, GREY, RESET = "\033[32m", "\033[31m", "\033[90m", "\033[0m"

HEADER = """# SupportPilot CA bundle — GENERATED, do not edit.
#
# The public root store, plus the local Keycloak certificate. Containers point SSL_CERT_FILE at
# this file rather than at keycloak.crt alone, because those variables *replace* the trust store:
# naming a single certificate leaves a container unable to verify anything else.
#
# Regenerate with: python scripts/build_ca_bundle.py
"""


def public_roots() -> tuple[str, int]:
    """The public root store, from certifi — the bundle Python HTTP clients use by default."""
    try:
        import certifi
    except ImportError:
        raise SystemExit(
            f"{RED}certifi is not installed on the host; run: python -m pip install certifi{RESET}"
        ) from None
    text = Path(certifi.where()).read_text(encoding="utf-8")
    return text, text.count("BEGIN CERTIFICATE")


def main() -> int:
    if not KEYCLOAK_CERT.exists():
        raise SystemExit(
            f"{RED}{KEYCLOAK_CERT.relative_to(REPO)} is missing; "
            f"run scripts/enable_keycloak_tls.py first{RESET}"
        )

    roots, count = public_roots()
    local = KEYCLOAK_CERT.read_text(encoding="utf-8")

    if "BEGIN CERTIFICATE" not in local:
        raise SystemExit(f"{RED}{KEYCLOAK_CERT.name} does not contain a PEM certificate{RESET}")

    BUNDLE.write_text(
        HEADER + "\n" + roots.rstrip() + "\n\n# --- local Keycloak ---\n" + local.strip() + "\n",
        encoding="utf-8",
    )

    total = BUNDLE.read_text(encoding="utf-8").count("BEGIN CERTIFICATE")
    print(f"{GREEN}wrote{RESET} {BUNDLE.relative_to(REPO)}")
    print(f"{GREY}  {count} public root(s) + 1 local certificate = {total} total{RESET}")
    if total != count + 1:
        raise SystemExit(f"{RED}unexpected certificate count; refusing to trust this bundle{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
