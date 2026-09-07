# ADR-0002 — Onyx in the local environment

- **Status:** Accepted
- **Date:** 2026-09-07
- **Deciders:** Engineering lead, Onyx owner, Security lead

## Context

Onyx runs the agent loop and calls SupportPilot's registered actions. The local environment needs it
for the tasks that are genuinely about Onyx (`P1-04` OAuth forwarding, `P1-16` action registration,
`P2-12` budgets, the `TS-7` abuse suite), but the standard Onyx deployment is a large stack —
Next.js web, FastAPI API server, background workers, Postgres, Vespa, Redis, MinIO, Nginx.

Two facts from the Onyx documentation decide this:

1. **Lite mode exists.** It runs the Chat UI and Agents without the Vespa index and background
   workers, in under 1 GB of memory — intended for teams interested only in chat and agents, which
   is exactly SupportPilot's use of it.
2. **Onyx supports `passthrough_auth` on custom actions**, forwarding the calling user's credentials
   to the API instead of a fixed credential, for APIs that enforce per-user authentication. This is
   the mechanism FR-02 and `P1-04` require, and it is a first-class feature rather than a workaround.

Onyx also supports self-hosted model providers (Ollama, LiteLLM, vLLM), so a paid model key is not a
prerequisite for local work.

## Decision

**Onyx runs in Lite mode under a separate Compose profile (`--profile onyx`), off by default.**

```bash
docker compose up -d                  # SupportPilot + Keycloak + OPA + PostgreSQL
docker compose --profile onyx up -d   # adds Onyx when agent work is being done
```

## Rationale

Onyx is the **caller**, not part of the enforcement boundary. The trust boundary is API → OPA →
PostgreSQL, and every control the release depends on is provable without a model in the loop:

- `T-001`…`T-007` and `V-01`…`V-12` exercise the API directly with a real Keycloak-issued user token.
- SP-OPS-001 §1 states the release does not depend on the model consistently refusing unsafe
  requests. Tests that *require* Onyx to run would quietly contradict that.

So the default environment is the one that proves the security properties, and Onyx is brought up for
the tasks that are actually about Onyx. This keeps the per-commit suites fast and keeps a model
provider off the critical path for phase 1.

## Consequences

- `P1-04` and `P1-16` must be run with the profile enabled, and their evidence records that Onyx was
  running and that `passthrough_auth` was configured — not a fixed credential.
- A direct-token test harness (`scripts/get-token.ps1`) exists so the API can be exercised without
  Onyx. It is a **test harness only**: it obtains a normal user token from Keycloak. It grants no
  authority the browser flow would not, and it is never a substitute for `P1-04` evidence.
- `TS-7` (agent abuse) inherently needs the profile. It is a per-phase suite, not a per-commit one,
  which matches the cost.
- If Lite mode turns out to lack an actions capability the design needs, the fallback is standard
  mode locally — a resource cost, not a design change. Recorded as a watch item under R-01.

## Sources

- [Onyx deployment overview](https://docs.onyx.app/deployment/overview)
- [Onyx OpenAPI actions](https://docs.onyx.app/admins/actions/openapi)
- [onyx-dot-app/onyx](https://github.com/onyx-dot-app/onyx)
