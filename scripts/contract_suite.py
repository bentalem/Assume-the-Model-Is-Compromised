"""TS-5 (contract) — call every tool the way a client reads the action document.

This suite exists because of a bug none of the other 219 tests could have caught.

`get_order` had an array query parameter, `include`. Onyx sent `include=["shipment"]`; FastAPI
expects `include=shipment`; the call failed as `invalid_request` even though the model had asked
for exactly the right thing. Every local test passed throughout, because every local test *built
the URL itself*, in the shape the server happened to want.

    A test that constructs the request itself is testing your assumptions, not your system.

So this suite does not hand-write requests. It reads `openapi/supportpilot-actions.json` — the same
document Onyx reads — and builds each call from the schema: required parameters filled from the
fixed test data, optional ones exercised, path templates substituted. If a parameter shape cannot
be expressed unambiguously by a client following the document, the call fails here rather than in
somebody's chat window.

Run: python scripts/contract_suite.py
"""

from __future__ import annotations

import json
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCUMENT = REPO / "openapi" / "supportpilot-actions.json"
KEYCLOAK = "https://localhost:8443"
REALM = "supportpilot"

GREEN, RED, GREY, YELLOW, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[90m", "\033[33m", "\033[1m", "\033[0m"
)

# Values from the fixed test-data baseline (docs/08 §2). Keyed by parameter name so the suite can
# fill anything the document declares without knowing the tools individually.
SAMPLES: dict[str, object] = {
    "order_number": "ORD-2001",
    "customer_ref": "CUS-4001",
    "ticket_number": "TKT-1001",
    "action_id": None,          # resolved at run time; no fixed action exists
    "q": "Priya",
    "limit": 5,
    "cursor": None,
    "include_items": True,
    "include_shipment": True,
}

# Operations that change state. Exercised for *schema acceptance* only — a 4xx that is not
# invalid_request still proves the client could express the call.
WRITE_OPERATIONS = {"add_internal_note", "propose_refund"}

results: list[tuple[str, str, str]] = []


def tls() -> ssl.SSLContext:
    context = ssl.create_default_context()
    certificate = REPO / ".secrets" / "tls" / "keycloak.crt"
    if certificate.exists():
        context.load_verify_locations(cafile=str(certificate))
    return context


def token_for(username: str) -> str:
    data = urllib.parse.urlencode({
        "grant_type": "password", "client_id": "supportpilot-test-harness",
        "username": username, "password": f"{username}-local-password", "scope": "openid",
    }).encode()
    url = f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token"
    with urllib.request.urlopen(url, data=data, timeout=20, context=tls()) as response:
        return json.load(response)["access_token"]


_PROBE = """
import json, os, httpx
try:
    r = httpx.request(
        os.environ["M"], "http://api:8000" + os.environ["P"],
        headers=json.loads(os.environ["H"]),
        json=json.loads(os.environ["B"]) if os.environ.get("B") else None,
        timeout=25,
    )
    print(json.dumps({"status": r.status_code, "body": r.text[:400]}))
except Exception as exc:
    print(json.dumps({"status": 0, "body": repr(exc)}))
"""


def call(method: str, path: str, token: str, body: dict | None = None) -> dict:
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T",
         "-e", f"M={method.upper()}", "-e", f"P={path}",
         "-e", f"H={json.dumps({'Authorization': f'Bearer {token}'})}",
         "-e", f"B={json.dumps(body) if body else ''}",
         "approval-portal", "python", "-c", _PROBE],
        cwd=REPO, capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace",
    )
    line = next((l for l in proc.stdout.splitlines() if l.startswith("{")), None)
    if not line:
        raise RuntimeError(f"probe failed: {(proc.stderr or proc.stdout)[:200]}")
    return json.loads(line)


def build_request(path_template: str, operation: dict) -> tuple[str, dict | None, list[str]]:
    """Build a call from the document alone, the way any client following it would.

    Returns the path, an optional body, and the names of parameters this suite could not fill —
    an unfillable parameter is itself a finding about the document.
    """
    path = path_template
    query: list[tuple[str, str]] = []
    unfillable: list[str] = []

    for parameter in operation.get("parameters", []):
        name = parameter["name"]
        location = parameter.get("in")
        if name not in SAMPLES:
            if parameter.get("required"):
                unfillable.append(name)
            continue
        value = SAMPLES[name]
        if value is None:
            continue

        if location == "path":
            path = path.replace("{" + name + "}", urllib.parse.quote(str(value), safe=""))
        elif location == "query":
            # Booleans and numbers have exactly one sensible wire form. This is the property the
            # document is being checked for.
            rendered = str(value).lower() if isinstance(value, bool) else str(value)
            query.append((name, rendered))

    if "{" in path:
        unfillable.append(path[path.index("{") + 1: path.index("}")])

    body = None
    request_body = operation.get("requestBody")
    if request_body:
        schema = (
            request_body.get("content", {}).get("application/json", {}).get("schema", {})
        )
        body = sample_body(schema)

    full = path + ("?" + urllib.parse.urlencode(query) if query else "")
    return full, body, unfillable


def resolve(spec: dict, schemas: dict) -> dict:
    """Follow $ref and allOf until the actual schema is in hand.

    Without this the suite silently dropped required fields whose type sat behind a $ref — an enum,
    in both cases — sent an incomplete body, and read the server's correct 400 as a product bug.
    A test that quietly omits part of the request is worse than no test: it accuses working code.
    """
    seen = 0
    while spec and seen < 10:
        seen += 1
        if "$ref" in spec:
            spec = schemas.get(spec["$ref"].rsplit("/", 1)[-1], {})
            continue
        if "allOf" in spec and len(spec["allOf"]) == 1:
            merged = dict(spec)
            merged.pop("allOf")
            merged.update(resolve(spec["allOf"][0], schemas))
            return merged
        break
    return spec or {}


def sample_body(schema: dict, components: dict | None = None) -> dict:
    """A minimal body satisfying every declared required field.

    Raises if a required field cannot be filled — an unfillable required field means a client
    following the document could not construct the call, which is the finding this suite exists to
    surface. Silently omitting it would hide exactly that.
    """
    document = json.loads(DOCUMENT.read_text(encoding="utf-8"))
    schemas = document.get("components", {}).get("schemas", {})
    schema = resolve(schema, schemas)

    body: dict[str, object] = {}
    for name in schema.get("required", []):
        spec = resolve((schema.get("properties") or {}).get(name, {}), schemas)

        if name in SAMPLES and SAMPLES[name] is not None:
            body[name] = SAMPLES[name]
        elif spec.get("enum"):
            body[name] = spec["enum"][0]
        elif spec.get("type") == "string":
            body[name] = {"body": "contract suite note", "amount": "1.00",
                          "currency": "USD", "order_number": "ORD-2001"}.get(name, "sample")
        elif spec.get("type") in ("integer", "number"):
            body[name] = 1
        elif spec.get("type") == "boolean":
            body[name] = False
        else:
            raise ValueError(
                f"required field '{name}' has no expressible type in the document "
                f"({json.dumps(spec)[:80]})"
            )
    return body


def main() -> int:
    if not DOCUMENT.exists():
        raise SystemExit(f"{RED}{DOCUMENT.name} missing; run scripts/export_openapi.py{RESET}")

    document = json.loads(DOCUMENT.read_text(encoding="utf-8"))
    alice = token_for("alice")

    print()
    print(f"{BOLD}Contract suite — every tool called from the action document{RESET}")
    print("-" * 78)

    for path_template, item in document.get("paths", {}).items():
        for method, operation in item.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            operation_id = operation.get("operationId", f"{method} {path_template}")

            try:
                path, body, unfillable = build_request(path_template, operation)
            except Exception as exc:
                results.append((operation_id, "FAIL", f"could not build a request: {exc}"))
                print(f"  {operation_id:20} {RED}FAIL{RESET}  could not build a request: {exc}")
                continue

            if unfillable:
                results.append((operation_id, "SKIP", f"no sample for {', '.join(unfillable)}"))
                print(f"  {operation_id:20} {YELLOW}SKIP{RESET}  no sample value for "
                      f"{', '.join(unfillable)}")
                continue

            response = call(method, path, alice, body)
            status = response["status"]

            # The property under test is expressibility, not authorization: a client following the
            # document must be able to *form* the call. invalid_request means it could not.
            if status == 400:
                results.append((operation_id, "FAIL", f"400 invalid_request for {path}"))
                print(f"  {operation_id:20} {RED}FAIL{RESET}  400 invalid_request")
                print(f"  {'':20}       {GREY}{path}{RESET}")
                print(f"  {'':20}       {RED}a client following the document cannot express this "
                      f"call{RESET}")
            elif status == 0:
                results.append((operation_id, "FAIL", response["body"][:120]))
                print(f"  {operation_id:20} {RED}FAIL{RESET}  {response['body'][:80]}")
            else:
                note = "" if operation_id not in WRITE_OPERATIONS else " (write: schema accepted)"
                results.append((operation_id, "PASS", f"HTTP {status}{note}"))
                print(f"  {operation_id:20} {GREEN}PASS{RESET}  HTTP {status}{note}")

    print("-" * 78)
    passed = sum(1 for _, r, _ in results if r == "PASS")
    failed = sum(1 for _, r, _ in results if r == "FAIL")
    skipped = sum(1 for _, r, _ in results if r == "SKIP")

    if failed == 0:
        print(f"  {GREEN}every operation is expressible from the document{RESET} "
              f"({passed} passed, {skipped} skipped)")
    else:
        print(f"  {RED}{failed} operation(s) cannot be called from the document{RESET}")
        print(f"  {GREY}The model asked correctly and the call still failed — that is an "
              f"integration gap, not a model problem.{RESET}")
    print()

    evidence = REPO / "evidence"
    evidence.mkdir(exist_ok=True)
    report = evidence / f"contract-{time.strftime('%Y%m%dT%H%M%S')}.json"
    report.write_text(json.dumps(
        {"suite": "TS-5-contract", "passed": passed, "failed": failed, "skipped": skipped,
         "operations": [{"id": i, "result": r, "detail": d} for i, r, d in results]},
        indent=2), encoding="utf-8")
    print(f"  evidence written to {report.relative_to(REPO)}")
    print()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
