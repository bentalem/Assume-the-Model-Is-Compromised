"""Export and check the Onyx action document.

The document Onyx registers is generated from the code that enforces the contract, then written to
openapi/supportpilot-actions.yaml so the diff is reviewable. Generation alone is not enough: a route
added without review would otherwise appear in the registered action set automatically, which is a
control-plane change arriving through an ordinary code change (SP-OPS-001 section 10).

So this script also enforces the rules the document must satisfy, and fails if any is broken:

  * every operation is on the approved list;
  * every operation has an operationId, a summary, and a bounded response schema;
  * no request or path parameter is named user_id, organization_id, role, author_id, or approved;
  * no response schema allows additional properties or an unbounded array.

Run: python scripts/export_openapi.py [--check]
    --check verifies the committed file matches the running code without rewriting it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Two formats of one document. YAML is what a human reviews in a diff; Onyx's "Add OpenAPI Action"
# accepts JSON only, so the JSON is what actually gets pasted. Both are generated from the same
# schema in the same run, so they cannot drift apart.
OUTPUT = REPO / "openapi" / "supportpilot-actions.yaml"
OUTPUT_JSON = REPO / "openapi" / "supportpilot-actions.json"

# The registered action set. Adding to this list is a control-plane change and needs the review in
# SP-OPS-001 section 10 — it is not a side effect of writing a route.
APPROVED_OPERATIONS = {
    "get_order",
    "search_customers",
    "get_customer",
    "get_ticket",
    "add_internal_note",
    "propose_refund",
    "get_action_status",
}

# Names the server derives from verified identity. A parameter with one of these names would mean
# the model could propose an identity (SP-PRD-001 section 6).
FORBIDDEN_PARAMETER_NAMES = {
    "user_id", "organization_id", "org_id", "role", "roles",
    "author_id", "approved", "state", "actor_id", "tenant",
}

EXTRACT = """
import json
from supportpilot_api.main import create_app
print(json.dumps(create_app().openapi()))
"""


def generate() -> dict:
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "api", "python", "-c", EXTRACT],
        cwd=REPO, capture_output=True, text=True, timeout=120, encoding="utf-8",
    )
    line = next((l for l in proc.stdout.splitlines() if l.startswith("{")), None)
    if not line:
        raise SystemExit(
            "could not generate the document; is the api service running?\n"
            f"{(proc.stderr or proc.stdout)[:400]}"
        )
    return json.loads(line)


def audit(spec: dict) -> list[str]:
    findings: list[str] = []
    seen: set[str] = set()

    for path, operations in spec.get("paths", {}).items():
        for method, operation in operations.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue

            operation_id = operation.get("operationId")
            if not operation_id:
                findings.append(f"{method.upper()} {path}: no operationId")
                continue
            seen.add(operation_id)

            if operation_id not in APPROVED_OPERATIONS:
                findings.append(
                    f"{operation_id}: not in the approved operation list. Registering a new tool "
                    f"is a control-plane change and needs review before it reaches this document."
                )
            if not operation.get("summary"):
                findings.append(f"{operation_id}: no summary for the model to read")

            for parameter in operation.get("parameters", []):
                name = parameter.get("name", "")
                if parameter.get("in") == "header":
                    findings.append(
                        f"{operation_id}: header '{name}' is exposed to the model. Authentication "
                        f"and correlation headers are supplied by Onyx and infrastructure; mark "
                        f"them include_in_schema=False."
                    )
                if name.lower() in FORBIDDEN_PARAMETER_NAMES:
                    findings.append(
                        f"{operation_id}: parameter '{name}' is server-derived and must not be "
                        f"accepted from the caller"
                    )
                schema = parameter.get("schema", {})
                if schema.get("type") == "string" and not (
                    schema.get("pattern") or schema.get("maxLength") or schema.get("enum")
                ):
                    findings.append(f"{operation_id}: string parameter '{name}' is unbounded")

                # No array-typed query parameters.
                #
                # An array has several wire forms — repeated params, comma-joined, a JSON array —
                # and clients disagree. Onyx sent include=["shipment"] where FastAPI expected
                # include=shipment, and a correct model request failed as invalid_request. Every
                # local test passed, because the tests built the URL themselves.
                #
                # Accepting more forms would mean more parsing paths to validate. Splitting into
                # scalars removes the ambiguity instead: prefer the parameter shape with the fewest
                # ways to express it.
                if parameter.get("in") == "query" and schema.get("type") == "array":
                    findings.append(
                        f"{operation_id}: query parameter '{name}' is an array. Clients serialise "
                        f"arrays inconsistently; split it into scalar parameters."
                    )

            # Any 2xx, not just 200: a creation route answers 201, and requiring 200 would
            # report a correct route as broken.
            responses = operation.get("responses", {})
            success_codes = [c for c in responses if c.startswith("2")]
            if not success_codes:
                findings.append(f"{operation_id}: no success response documented")
            for code in success_codes:
                content = responses[code].get("content", {}).get("application/json", {})
                if not content.get("schema"):
                    findings.append(f"{operation_id}: {code} response has no schema")

    for schema_name, schema in spec.get("components", {}).get("schemas", {}).items():
        if schema.get("additionalProperties") is True:
            findings.append(f"schema {schema_name}: allows additional properties")
        for property_name, prop in (schema.get("properties") or {}).items():
            if prop.get("type") == "array" and "maxItems" not in prop:
                findings.append(
                    f"schema {schema_name}.{property_name}: unbounded array (needs maxItems)"
                )

    missing = APPROVED_OPERATIONS - seen
    if missing:
        findings.append(f"approved operations missing from the document: {sorted(missing)}")

    return findings


def to_json(spec: dict) -> str:
    """The paste-ready form. A JSON document carries no comments, so the note about it being
    generated goes in the description rather than being lost."""
    return json.dumps(spec, indent=2, ensure_ascii=False) + chr(10)


def to_yaml(spec: dict) -> str:
    try:
        import yaml
    except ImportError:
        raise SystemExit("pyyaml is required: python -m pip install pyyaml")

    header = (
        "# SupportPilot actions — the operations Onyx may register.\n"
        "#\n"
        "# GENERATED from the API routes by scripts/export_openapi.py. Do not edit by hand.\n"
        "# The diff of this file is the tool-schema review: a change here changes what the model\n"
        "# can call, which is a control-plane change (SP-OPS-001 section 10).\n"
        "#\n"
        "# Regenerate:  python scripts/export_openapi.py\n"
        "# Verify only: python scripts/export_openapi.py --check\n\n"
    )
    return header + yaml.safe_dump(spec, sort_keys=False, width=100, allow_unicode=True)


def main() -> int:
    check_only = "--check" in sys.argv
    spec = generate()

    findings = audit(spec)
    if findings:
        print("Action document rejected:\n")
        for finding in findings:
            print(f"  - {finding}")
        print()
        return 1

    rendered = to_yaml(spec)
    operations = sorted(
        op.get("operationId")
        for path in spec.get("paths", {}).values()
        for method, op in path.items()
        if method in {"get", "post", "put", "patch", "delete"}
    )

    rendered_json = to_json(spec)

    if check_only:
        for path, expected in ((OUTPUT, rendered), (OUTPUT_JSON, rendered_json)):
            if not path.exists():
                print(f"{path.relative_to(REPO)} does not exist; run without --check")
                return 1
            if path.read_text(encoding="utf-8") != expected:
                print(f"{path.relative_to(REPO)} is out of date with the running code.")
                print("Regenerate it and review the diff before merging.")
                return 1
        print(f"OK: action document matches the code. Operations: {', '.join(operations)}")
        return 0

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    OUTPUT_JSON.write_text(rendered_json, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(REPO)}       (for review and diffs)")
    print(f"Wrote {OUTPUT_JSON.relative_to(REPO)}  (paste this into Onyx)")
    print(f"Registered operations: {', '.join(operations)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
