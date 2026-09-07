# ADR-0001 — Implementation stack

- **Status:** Accepted
- **Date:** 2026-09-07
- **Deciders:** Engineering lead, Product owner

## Context

The design baseline (SP-PRD-001 … SP-OPS-001) deliberately specifies boundaries, not languages. The
API and worker need a stack that makes the baseline's requirements cheap to satisfy rather than
something to be bolted on:

- **Strict tool schemas** with length limits, type checks, enumerations, business constraints.
- **OpenAPI 3.1** document that Onyx registers as an action, containing only approved operations
  with bounded response schemas.
- **Parameterized SQL** with explicit transaction control (`SET LOCAL` per request).
- Fast local test cycle for the authorization suites, which run per commit.

## Decision

**Python 3.12 + FastAPI + Pydantic v2 + psycopg 3** for the API, worker, and approval portal.

- FastAPI emits OpenAPI 3.1 directly from the route signatures, so the registered action document is
  generated from the code that enforces the contract rather than maintained beside it.
- Pydantic v2 models give the strict request and response schemas the baseline requires, and
  `model_config = ConfigDict(extra="forbid")` makes "reject unknown fields" the default rather than
  an added check — which is what stops a model-supplied `organization_id` from being silently ignored.
- psycopg 3 exposes explicit transactions and server-side parameter binding, which is what the
  `BEGIN; SET LOCAL …; SELECT` pattern needs. No ORM: the baseline forbids generated SQL and requires
  named columns, so hand-written parameterized statements in repository modules are the honest fit.
- Python is already installed on the build machine, so the policy and database suites run locally
  without a container round-trip.

## Consequences

- Response minimization is enforced by declaring `response_model` on every route; a field absent from
  the model cannot leak even if the repository returns it.
- The OpenAPI document must be **exported and reviewed**, not merely generated — a route added
  without review would otherwise appear in the action document automatically. Export is a build step
  and the diff is part of tool-schema review (SP-OPS-001 §10).
- Python's dynamic typing means the `no user_id/organization_id in request` rule needs an explicit
  test, not just a type. That test exists as `TS1-12`.

## Alternatives considered

- **TypeScript + Fastify** — equally viable; rejected only because OpenAPI 3.1 emission needs an
  extra layer and Node is not installed here.
- **Go + chi** — best deployment story, but schemas and the OpenAPI document would be hand-written,
  which is more code for the same guarantees at this stage.
