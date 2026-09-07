"""Give Keycloak TLS, so Onyx will accept it as an identity provider.

Onyx refuses a plain-HTTP IdP: `validate_idp_url` passes `https_only=True`, hardcoded, and applies
the same check to every endpoint the discovery document names. There is no setting to relax it, and
there should not be — an OIDC discovery document fetched over HTTP is trivially forgeable.

So this is not a workaround for Onyx. SP-ARCH-001 §8 already requires internal HTTPS; the local
environment simply had not implemented it yet.

What this does:
  * generates a self-signed certificate valid for the names Keycloak is reached by — `localhost`
    for the browser and `keycloak` for containers, in one certificate with both SANs, because the
    same document is fetched over both;
  * points Keycloak at it and moves the published port to 8443;
  * mounts the certificate into the SupportPilot API as a trusted CA, so its JWKS fetch verifies;
  * writes an override file that does the same for Onyx.

The certificate and key live in .secrets/tls/ and are not committed.

Run: python scripts/enable_keycloak_tls.py
"""

from __future__ import annotations

import datetime
import ipaddress
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TLS_DIR = REPO / ".secrets" / "tls"
CERT = TLS_DIR / "keycloak.crt"
KEY = TLS_DIR / "keycloak.key"
ONYX_OVERRIDE = REPO / "infrastructure" / "local" / "onyx" / "docker-compose.supportpilot.yml"

GREEN, YELLOW, GREY, BOLD, RESET = "\033[32m", "\033[33m", "\033[90m", "\033[1m", "\033[0m"

# One certificate, every name Keycloak answers to. A browser reaches it as localhost; containers on
# the app network reach it as keycloak. Both must validate against the same certificate, because
# both fetch parts of the same discovery document.
SAN_DNS = ["localhost", "keycloak", "supportpilot-keycloak", "host.docker.internal"]
SAN_IP = ["127.0.0.1"]


def step(message: str) -> None:
    print(f"{YELLOW}==>{RESET} {message}")


def ok(message: str) -> None:
    print(f"    {GREEN}ok{RESET}  {message}")


def generate_certificate() -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    TLS_DIR.mkdir(parents=True, exist_ok=True)
    if CERT.exists() and KEY.exists():
        ok("certificate already present in .secrets/tls/")
        return

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "keycloak"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SupportPilot local development"),
    ])
    alternatives = [x509.DNSName(n) for n in SAN_DNS] + [
        x509.IPAddress(ipaddress.ip_address(a)) for a in SAN_IP
    ]
    now = datetime.datetime.now(datetime.UTC)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)  # self-signed: it is its own CA, so clients trust this one file
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(alternatives), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    CERT.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    KEY.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    ok(f"generated a certificate for {', '.join(SAN_DNS)} (365 days)")


def patch_compose() -> None:
    path = REPO / "compose.yaml"
    content = path.read_text(encoding="utf-8")
    if "KC_HTTPS_CERTIFICATE_FILE" in content:
        ok("compose.yaml already configured for TLS")
        return

    content = content.replace(
        """        exec /opt/keycloak/bin/kc.sh start-dev --import-realm --http-port=8080""",
        """        exec /opt/keycloak/bin/kc.sh start-dev --import-realm \\
             --http-port=8080 --https-port=8443""",
    )
    content = content.replace(
        """      KC_HOSTNAME: http://localhost:8080""",
        """      # HTTPS, because Onyx refuses a plain-HTTP identity provider and SP-ARCH-001 §8 asks
      # for internal HTTPS regardless. The certificate covers both names, so the browser reaching
      # localhost and containers reaching keycloak validate against the same file.
      KC_HTTPS_CERTIFICATE_FILE: /opt/keycloak/conf/tls/keycloak.crt
      KC_HTTPS_CERTIFICATE_KEY_FILE: /opt/keycloak/conf/tls/keycloak.key
      KC_HOSTNAME: https://localhost:8443""",
    )
    content = content.replace(
        """      - ./infrastructure/local/keycloak:/opt/keycloak/data/import:ro""",
        """      - ./infrastructure/local/keycloak:/opt/keycloak/data/import:ro
      - ./.secrets/tls:/opt/keycloak/conf/tls:ro""",
    )
    content = content.replace(
        """    ports:
      # Local only. The user-facing login flow and the token endpoint the test harness calls.
      - "127.0.0.1:8080:8080\"""",
        """    ports:
      # Local only. The user-facing login flow and the token endpoint the test harness calls.
      # 8080 stays published so the plain-HTTP harness keeps working; 8443 is what Onyx uses.
      - "127.0.0.1:8080:8080"
      - "127.0.0.1:8443:8443\"""",
    )

    # The API verifies tokens against the HTTPS issuer and fetches keys over the internal name.
    content = content.replace(
        "KEYCLOAK_ISSUER:-http://localhost:8080/realms/supportpilot",
        "KEYCLOAK_ISSUER:-https://localhost:8443/realms/supportpilot",
    )
    content = content.replace(
        "KEYCLOAK_JWKS_URL:-http://keycloak:8080/realms/supportpilot/protocol/openid-connect/certs",
        "KEYCLOAK_JWKS_URL:-https://keycloak:8443/realms/supportpilot/protocol/openid-connect/certs",
    )
    content = content.replace(
        """    secrets:
      - api_db_password
    # No published port, deliberately.""",
        """      # Trust the local Keycloak certificate for the JWKS fetch. Scoped to this one
      # certificate rather than disabling verification.
      SSL_CERT_FILE: /etc/ssl/supportpilot/keycloak.crt
    volumes:
      - ./.secrets/tls:/etc/ssl/supportpilot:ro
    secrets:
      - api_db_password
    # No published port, deliberately.""",
    )
    path.write_text(content, encoding="utf-8")
    ok("compose.yaml updated: Keycloak serves HTTPS on 8443, API trusts the certificate")

    # .env wins over the ${VAR:-default} forms in compose, so leaving it behind silently keeps the
    # API on the old HTTP issuer and every token is rejected as claims_or_signature_invalid — a
    # failure that looks like a signing problem and is not.
    replacements = {
        "KEYCLOAK_ISSUER=http://localhost:8080/realms/supportpilot":
            "KEYCLOAK_ISSUER=https://localhost:8443/realms/supportpilot",
        "KEYCLOAK_JWKS_URL=http://keycloak:8080/realms/supportpilot/protocol/openid-connect/certs":
            "KEYCLOAK_JWKS_URL=https://keycloak:8443/realms/supportpilot/protocol/openid-connect/certs",
        "KEYCLOAK_PUBLIC_ISSUER=http://localhost:8080/realms/supportpilot":
            "KEYCLOAK_PUBLIC_ISSUER=https://localhost:8443/realms/supportpilot",
    }
    for env_file in (REPO / ".env", REPO / ".env.example"):
        if not env_file.exists():
            continue
        text = env_file.read_text(encoding="utf-8")
        for before, after in replacements.items():
            text = text.replace(before, after)
        env_file.write_text(text, encoding="utf-8")
    ok(".env and .env.example moved to the HTTPS issuer")


def write_onyx_override() -> None:
    ONYX_OVERRIDE.parent.mkdir(parents=True, exist_ok=True)
    ONYX_OVERRIDE.write_text(
        """# SupportPilot overlay for Onyx.
#
# Apply alongside Onyx's own compose files:
#
#   cd ~/.config/onyx/deployment
#   docker compose -f docker-compose.yml -f docker-compose.onyx-lite.yml \\
#                  -f <path-to-this-file> up -d api_server
#
# It does two things Onyx cannot do for itself:
#
#   1. Joins api_server to SupportPilot's `app` network, so it can reach the action API at
#      http://api:8000 and Keycloak at https://keycloak:8443.
#   2. Mounts the local Keycloak certificate and points Python's TLS stack at it, so Onyx will
#      accept the identity provider. Scoped to this one certificate — verification stays on.
#
# Onyx refuses a plain-HTTP IdP (`https_only=True`, hardcoded in sso_url_guard.py) and applies the
# same rule to every endpoint the discovery document names, so both the certificate and the trust
# have to be real.

name: onyx

services:
  api_server:
    environment:
      # Both, because Onyx's stack mixes httpx/requests and raw ssl contexts.
      - SSL_CERT_FILE=/etc/ssl/supportpilot/keycloak.crt
      - REQUESTS_CA_BUNDLE=/etc/ssl/supportpilot/keycloak.crt
    volumes:
      - ${SUPPORTPILOT_TLS_DIR:?set SUPPORTPILOT_TLS_DIR to the .secrets/tls path}:/etc/ssl/supportpilot:ro
    networks:
      - default
      - supportpilot_app

networks:
  supportpilot_app:
    external: true
""",
        encoding="utf-8",
    )
    ok(f"wrote {ONYX_OVERRIDE.relative_to(REPO)}")


def main() -> int:
    print()
    print(f"{BOLD}Enabling TLS on Keycloak{RESET}")
    print("-" * 74)

    step("Generating the certificate")
    generate_certificate()

    step("Building the combined CA bundle")
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "build_ca_bundle.py")],
        cwd=REPO, capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise SystemExit(result.stdout + result.stderr)
    ok(result.stdout.strip().splitlines()[-1].strip())

    step("Updating compose.yaml")
    patch_compose()

    step("Writing the Onyx override")
    write_onyx_override()

    step("Restarting Keycloak and the API")
    result = subprocess.run(
        ["docker", "compose", "up", "-d", "--force-recreate", "keycloak", "api"],
        cwd=REPO, capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0:
        print(result.stderr[-1500:])
        raise SystemExit("failed to restart; see the output above")
    ok("restarted")

    print()
    print("-" * 74)
    print(f"{BOLD}Next{RESET}")
    print()
    print("1. Apply the override to Onyx so it trusts the certificate:")
    print(f"     {GREY}cd \"$HOME/.config/onyx/deployment\"{RESET}")
    print(f"     {GREY}SUPPORTPILOT_TLS_DIR='{TLS_DIR}' \\{RESET}")
    print(f"     {GREY}  docker compose -f docker-compose.yml -f docker-compose.onyx-lite.yml \\{RESET}")
    print(f"     {GREY}    -f '{ONYX_OVERRIDE}' up -d api_server{RESET}")
    print()
    print("2. In Onyx: Admin Panel -> Security -> set SSRF Protection to")
    print(f"   {BOLD}'Allow private network'{RESET}. The default blocks RFC1918 addresses, and")
    print(f"   {GREY}keycloak:8443 resolves to a Docker private address.{RESET}")
    print()
    print("3. Add the SSO provider with the HTTPS discovery URL:")
    print(f"   {BOLD}https://keycloak:8443/realms/supportpilot/.well-known/openid-configuration{RESET}")
    print()
    print(f"{GREY}Then: python scripts/connect_onyx.py && python scripts/verify_onyx_flow.py{RESET}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
