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

The memory service's document (openapi/supportpilot-memory-actions.*, track 9) is generated and held
to the same rules, plus one: no request body may carry a field the server decides — identity, the
write channel, a status, an approval. It is checked when the memory profile is running and skipped,
with a line saying so, when it is not.

Run: python scripts/export_openapi.py [--check]
    --check verifies the committed files match the running code without rewriting them.
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

# The memory service's action document (track 9): a second, separate registration, holding only the
# four operations the model may call. History, confirmation, summaries, rule decisions and context
# assembly are for an agent runtime and must never appear in it — a model that could confirm its own
# memories or approve its own rules would make both controls meaningless.
MEMORY_OUTPUT = REPO / "openapi" / "supportpilot-memory-actions.yaml"
MEMORY_OUTPUT_JSON = REPO / "openapi" / "supportpilot-memory-actions.json"
MEMORY_APPROVED_OPERATIONS = {"remember", "recall", "forget", "propose_rule"}

# One action document per delegation-broker profile (track 1, 1.5 - 1.8). Each is the main document
# cut down to the operations the profile's ceiling covers, pointed at the broker instead of the API.
# Derived, never written by hand: from the audited main document, the policy's scope table, the
# profiles file, and the broker's own operation table — whose test proves it matches this document.
# So a profile document can only ever be a subset of what was reviewed above, never an addition.
PROFILE_OUTPUT_DIR = REPO / "openapi" / "profiles"
PROFILES_FILE = REPO / "infrastructure" / "local" / "broker" / "profiles.json"
SCOPES_FILE = REPO / "policy" / "supportpilot" / "scopes.json"
BROKER_URL = "http://broker:8097"

# Names the server derives from verified identity. A parameter with one of these names would mean
# the model could propose an identity (SP-PRD-001 section 6).
FORBIDDEN_PARAMETER_NAMES = {
    "user_id", "organization_id", "org_id", "role", "roles",
    "author_id", "approved", "state", "actor_id", "tenant",
}

# For the memory document, also refused as a *request body* field. The API's gate checks parameters
# only; the memory service's whole write-path lesson is that the body cannot say who wrote something
# or whether it counts, so its gate checks the body too.
MEMORY_FORBIDDEN_BODY_FIELDS = FORBIDDEN_PARAMETER_NAMES | {
    "channel", "source", "status", "confirmed", "owner_sub", "user_sub", "decided_by",
}

MEMORY_EXTRACT = """
import json
from supportpilot_memory.main import create_app
print(json.dumps(create_app().openapi()))
"""

EXTRACT = """
import json
from supportpilot_api.main import create_app
print(json.dumps(create_app().openapi()))
"""


def generate(service: str = "api", extract: str = EXTRACT) -> dict:
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", service, "python", "-c", extract],
        cwd=REPO, capture_output=True, text=True, timeout=120, encoding="utf-8",
    )
    line = next((l for l in proc.stdout.splitlines() if l.startswith("{")), None)
    if not line:
        raise SystemExit(
            f"could not generate the document; is the {service} service running?\n"
            f"{(proc.stderr or proc.stdout)[:400]}"
        )
    return json.loads(line)


def inline_enum_refs(spec: dict) -> int:
    """Replace `$ref`s to plain enum schemas with the enum itself.

    Pydantic emits an Enum field as a reference into components/schemas. That is correct OpenAPI and
    it is a trap here: whether the caller ever sees the allowed values depends on whether its client
    resolves the reference. Onyx's did not, so `reason` reached the model as a field with no type and
    no list of values — and a refund proposal came back as `invalid_request` with the model saying,
    accurately, that the schema did not tell it what to send.

    A tool schema is read by something that cannot ask a follow-up question. It has to be
    self-contained at the property, not one lookup away.

    Only simple enums are inlined; object schemas keep their references, because inlining those
    would duplicate whole response models for no gain.
    """
    schemas = spec.get("components", {}).get("schemas", {})
    simple = {
        name: definition
        for name, definition in schemas.items()
        if set(definition) <= {"type", "enum", "title", "description"} and "enum" in definition
    }
    inlined = 0

    def walk(node):
        nonlocal inlined
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        for key, value in list(node.items()):
            if isinstance(value, dict):
                # Pydantic writes either {"$ref": ...} or, when the field carries its own
                # description, {"allOf": [{"$ref": ...}], "description": ...}. Both hide the values.
                reference, siblings = None, {}
                if "$ref" in value:
                    reference = value["$ref"]
                    siblings = {k: v for k, v in value.items() if k != "$ref"}
                elif (
                    isinstance(value.get("allOf"), list)
                    and len(value["allOf"]) == 1
                    and isinstance(value["allOf"][0], dict)
                    and "$ref" in value["allOf"][0]
                ):
                    reference = value["allOf"][0]["$ref"]
                    siblings = {k: v for k, v in value.items() if k != "allOf"}
                if reference:
                    name = reference.rsplit("/", 1)[-1]
                    if name in simple:
                        merged = {k: v for k, v in simple[name].items() if k != "title"}
                        # A description written on the field wins over the enum's own.
                        merged.update(siblings)
                        node[key] = merged
                        inlined += 1
                        continue
            walk(value)

    walk(spec.get("paths", {}))
    for definition in schemas.values():
        walk(definition.get("properties", {}))

    # And the request bodies themselves, for the same reason one level up.
    #
    # A body published as a reference is a POST with no fields as far as an unresolving client is
    # concerned. Onyx's model invented them: it put the currency inside the amount, omitted the
    # currency field, and wrote the reason as prose. Nothing was wrong with the schema — the model
    # never saw it. Response schemas keep their references: the caller reads those, it does not
    # have to construct them.
    for path_item in spec.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            body = operation.get("requestBody", {}).get("content", {})
            for media in body.values():
                reference = media.get("schema", {}).get("$ref")
                if not reference:
                    continue
                name = reference.rsplit("/", 1)[-1]
                definition = schemas.get(name)
                if definition and definition.get("type") == "object":
                    media["schema"] = json.loads(json.dumps(definition))
                    inlined += 1

    for name in simple:
        if not json.dumps(spec).count(f'"#/components/schemas/{name}"'):
            schemas.pop(name, None)
    return inlined


def audit(spec: dict, approved: set[str] | None = None,
          forbidden_body_fields: set[str] | None = None) -> list[str]:
    approved = APPROVED_OPERATIONS if approved is None else approved
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

            if operation_id not in approved:
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
            # A bare reference for a value set is how `reason` reached the model with no values.
            if "$ref" in prop and prop["$ref"].rsplit("/", 1)[-1] not in spec.get(
                "components", {}
            ).get("schemas", {}):
                findings.append(
                    f"schema {schema_name}.{property_name}: dangling reference {prop['$ref']}"
                )
            if prop.get("type") == "array" and "maxItems" not in prop:
                findings.append(
                    f"schema {schema_name}.{property_name}: unbounded array (needs maxItems)"
                )

    if forbidden_body_fields:
        # Request bodies only: a response may well report a status. inline_enum_refs has already
        # put every object body inline; a reference that survived is resolved here, not skipped.
        schemas = spec.get("components", {}).get("schemas", {})
        for path, operations in spec.get("paths", {}).items():
            for method, operation in operations.items():
                if not isinstance(operation, dict):
                    continue
                body = (operation.get("requestBody") or {}).get("content", {}).get(
                    "application/json", {}).get("schema", {})
                if "$ref" in body:
                    body = schemas.get(body["$ref"].rsplit("/", 1)[-1], {})
                if body and body.get("additionalProperties") is not False:
                    findings.append(f"{method.upper()} {path}: request body accepts fields it does "
                                    f"not declare (needs extra='forbid')")
                for property_name in (body.get("properties") or {}):
                    if property_name.lower() in forbidden_body_fields:
                        findings.append(f"{method.upper()} {path}: request body field "
                                        f"'{property_name}' is decided by the server and must not "
                                        f"be accepted from the caller")

    missing = approved - seen
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


def _broker_operations() -> dict[str, str]:
    """operationId -> policy action, from the broker's table rather than a third copy of it."""
    sys.path.insert(0, str(REPO / "services" / "broker" / "src"))
    try:
        from delegation_broker.operations import OPERATIONS
    finally:
        sys.path.pop(0)
    return {operation.operation_id: operation.action for operation in OPERATIONS}


def profile_documents(spec: dict) -> dict[str, str]:
    """Each profile's document, rendered. Raises if any operation cannot be placed."""
    scopes = json.loads(SCOPES_FILE.read_text(encoding="utf-8"))["scopes"]["actions"]
    profiles = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))["profiles"]
    actions = _broker_operations()
    documents: dict[str, str] = {}
    for profile in profiles:
        name, ceiling = profile["name"], set(profile["ceiling"])
        document = json.loads(json.dumps(spec))
        for path in list(document.get("paths", {})):
            for method in list(document["paths"][path]):
                operation = document["paths"][path][method]
                if not isinstance(operation, dict) or "operationId" not in operation:
                    continue
                action = actions.get(operation["operationId"])
                if action is None:
                    raise SystemExit(f"{operation['operationId']} is not in the broker's table")
                if scopes.get(action) not in ceiling:
                    del document["paths"][path][method]
            if not document["paths"][path]:
                del document["paths"][path]
        document["servers"] = [{
            "url": f"{BROKER_URL}/{name}",
            "description": f"The delegation broker, as the {name} profile. Every call is made with a "
                           f"token naming the user and {name}, narrowed to the call.",
        }]
        document.setdefault("info", {})["title"] = (
            f"{document.get('info', {}).get('title', 'SupportPilot')} — {name}")
        _prune_unreferenced_schemas(document)
        documents[name] = to_json(document)
    return documents


def _prune_unreferenced_schemas(document: dict) -> None:
    schemas = document.get("components", {}).get("schemas", {})
    while True:
        text = json.dumps({k: v for k, v in document.items() if k != "components"}) + json.dumps(
            schemas)
        unused = [n for n in schemas if f'"#/components/schemas/{n}"' not in text]
        if not unused:
            return
        for name in unused:
            schemas.pop(name)


def check_profile_documents(spec: dict) -> int:
    for name, expected in profile_documents(spec).items():
        path = PROFILE_OUTPUT_DIR / f"{name}.json"
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            print(f"{path.relative_to(REPO)} is out of date with the action document or the profiles.")
            return 1
    stale = {p.stem for p in PROFILE_OUTPUT_DIR.glob("*.json")} - set(profile_documents(spec))
    if stale:
        print(f"profile documents for unregistered profiles: {sorted(stale)}")
        return 1
    print(f"OK: profile action documents match the profiles: {', '.join(sorted(profile_documents(spec)))}")
    return 0


def write_profile_documents(spec: dict) -> None:
    PROFILE_OUTPUT_DIR.mkdir(exist_ok=True)
    documents = profile_documents(spec)
    for stale in PROFILE_OUTPUT_DIR.glob("*.json"):
        if stale.stem not in documents:
            stale.unlink()
    for name, text in documents.items():
        (PROFILE_OUTPUT_DIR / f"{name}.json").write_text(text, encoding="utf-8")
        print(f"Wrote {(PROFILE_OUTPUT_DIR / f'{name}.json').relative_to(REPO)}")


def main() -> int:
    check_only = "--check" in sys.argv
    spec = generate()

    inlined = inline_enum_refs(spec)

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
        return check_profile_documents(spec) or check_memory_document()

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    OUTPUT_JSON.write_text(rendered_json, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(REPO)}       (for review and diffs)")
    print(f"Wrote {OUTPUT_JSON.relative_to(REPO)}  (paste this into Onyx)")
    print(f"Registered operations: {', '.join(operations)}")
    write_profile_documents(spec)
    return write_memory_document()


def _memory_running() -> bool:
    proc = subprocess.run(["docker", "compose", "ps", "--status", "running", "--services"],
                          cwd=REPO, capture_output=True, text=True, timeout=60, encoding="utf-8")
    return "memory" in proc.stdout.split()


def _memory_spec() -> tuple[dict, list[str]]:
    spec = generate("memory", MEMORY_EXTRACT)
    inline_enum_refs(spec)
    return spec, audit(spec, MEMORY_APPROVED_OPERATIONS, MEMORY_FORBIDDEN_BODY_FIELDS)


def _memory_operations(spec: dict) -> list[str]:
    return sorted(op.get("operationId") for path in spec.get("paths", {}).values()
                  for method, op in path.items() if method in {"get", "post", "put", "patch", "delete"})


def _memory_yaml(spec: dict) -> str:
    return to_yaml(spec).replace(
        "# SupportPilot actions — the operations Onyx may register.",
        "# SupportPilot memory actions — the four memory operations Onyx may register (track 9).", 1)


def check_memory_document() -> int:
    # Skipped when the memory profile is down, for the reason the API check is skipped when the API
    # is down — but said out loud, so a skip is never mistaken for a pass.
    if not _memory_running():
        print("SKIP: memory action document not checked — the memory profile is not running.")
        return 0
    spec, findings = _memory_spec()
    if findings:
        print("Memory action document rejected:\n")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    for path, expected in ((MEMORY_OUTPUT, _memory_yaml(spec)), (MEMORY_OUTPUT_JSON, to_json(spec))):
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            print(f"{path.relative_to(REPO)} is out of date with the running memory service.")
            return 1
    print(f"OK: memory action document matches the code. Operations: "
          f"{', '.join(_memory_operations(spec))}")
    return 0


def write_memory_document() -> int:
    if not _memory_running():
        print("Memory profile not running; memory action document not regenerated.")
        return 0
    spec, findings = _memory_spec()
    if findings:
        print("Memory action document rejected:\n")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    MEMORY_OUTPUT.write_text(_memory_yaml(spec), encoding="utf-8")
    MEMORY_OUTPUT_JSON.write_text(to_json(spec), encoding="utf-8")
    print(f"Wrote {MEMORY_OUTPUT_JSON.relative_to(REPO)}  (the second action to paste into Onyx)")
    print(f"Memory operations: {', '.join(_memory_operations(spec))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
