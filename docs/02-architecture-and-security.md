# 02 — Architecture and security design

> Source: `02_SupportPilot_Architecture_and_Security.docx` (SP-ARCH-001 v1.0, 2026-09-07)

## 1. Principles

- Identity is established before the agent can use business tools.
- The model proposes; trusted services authorize and execute.
- Every security rule has an enforceable boundary **outside the prompt**.
- Tools expose business operations rather than infrastructure primitives.
- High-impact actions are separated into request, approval, and execution.
- The control plane has separate administrative identities and change records.
- Services and database roles follow least privilege and deny by default.
- Audit evidence is generated where trusted decisions and effects occur.

## 2. System context

Onyx provides the user-facing agent experience and runs the agent loop. The model chooses whether to
answer or request a registered tool. SupportPilot owns business authorization, database access,
action state, and audit evidence. Keycloak owns authentication. OPA evaluates policy. PostgreSQL
stores business and security state. The worker executes only approved jobs.

## 3. Components

| Component | Responsibility | Must not do |
|---|---|---|
| Onyx | Chat, agent config, model interaction, action invocation | Connect directly to PostgreSQL or decide business authorization |
| Model | Interpret requests, select tools, write answers | Hold credentials, approve actions, execute effects |
| Keycloak | Authenticate users, issue signed tokens | Use model claims or chat text as identity evidence |
| Reverse proxy | Terminate TLS, route, apply request limits | Replace application authorization |
| SupportPilot API | Verify tokens, validate tools, request decisions, query data, create action requests | Execute protected financial effects in the synchronous request |
| OPA | Evaluate structured input against versioned policy | Query business data directly or enforce the decision |
| PostgreSQL | Store records, enforce grants and row policies, maintain transactions | Accept connections from Onyx or the public network |
| Approval portal | Show exact action details, capture independent decisions | Modify the payload after approval |
| Worker | Claim approved jobs, execute allowlisted effects once | Accept model instructions or arbitrary destinations |
| Migration job | Apply reviewed schema and policy changes at deploy | Run continuously or expose credentials to runtime services |

## 4. Trust boundaries

| Boundary | Untrusted side | Trusted control |
|---|---|---|
| User → Onyx | User messages and attachments | Authentication, session controls, content limits |
| Onyx → model | Model output may be wrong or manipulated | Strict tool schemas, loop limits, external authorization |
| Onyx → SupportPilot | Tool names and arguments originate from the model | Token verification, schema validation, allowlisted routes |
| SupportPilot → OPA | Application input may be incomplete | Server builds input from verified identity and trusted resource data |
| SupportPilot → PostgreSQL | Application bugs and injection attempts | Parameterized statements, grants, RLS, transactions |
| Approval → worker | Stale or modified action state | Immutable payload hash, state checks, approver identity, idempotency |
| Worker → provider | Provider errors, retries, compromised destinations | Allowlisted adapter, short-lived credential, timeout, result verification |

## 5. Control plane vs data plane

| Plane | Includes | Identity examples |
|---|---|---|
| Control | Agent prompts, tool registration, OPA bundles, deployments, migrations, secrets, admin settings | Onyx administrator, policy publisher, deployment identity, migration role |
| Data | User chats, model calls, tool execution, reads, proposals, approvals, worker jobs, audit events | Authenticated support user, API workload identity, worker workload identity |

**Required boundary:** a user-facing service cannot register a new tool, change an approval rule,
publish policy, alter database grants, or grant itself a new infrastructure permission.

Control-plane protections: separate administrator accounts with MFA · reviewed changes in version
control · protected branches and deployment approvals for policy, tool, and schema changes · no
control-plane credential mounted into the API or worker · change records identifying author,
reviewer, version, time, and result.

## 6. Read flow

```
user → Onyx → model → (tool request) → Onyx → API
                                              ├─ verify token (Keycloak keys)
                                              ├─ load trusted resource attributes
                                              ├─ ask OPA → allow/deny + obligations
                                              ├─ BEGIN; SET LOCAL context; parameterized query
                                              │    └─ PostgreSQL grants + RLS filter rows
                                              ├─ apply field obligations
                                              └─ write audit event; COMMIT
                                        → bounded result → Onyx → model → answer
```

The model never receives database credentials and never writes SQL. The loop continues until the
model returns a final answer or reaches a configured limit.

## 7. Sensitive action flow

| State | Who may create the transition | Required checks |
|---|---|---|
| `PROPOSED` | SupportPilot API | Authorized requester, valid resource, schema, business limits |
| `PENDING_APPROVAL` | SupportPilot API | Approval rule selected and immutable payload hash stored |
| `APPROVED` | Approval portal | Authorized independent approver, current action, exact payload |
| `REJECTED` | Approval portal | Authorized approver and recorded reason |
| `QUEUED` | Action coordinator | Valid unexpired approval and no prior execution |
| `EXECUTING` | Worker | Atomic job claim and idempotency reservation |
| `SUCCEEDED` | Worker | Provider outcome verified and reference recorded |
| `FAILED` | Worker | Error classified, attempt recorded, retry policy applied |

## 8. Network design

| Source | Destination | Purpose | Rule |
|---|---|---|---|
| User network | Reverse proxy | HTTPS to Onyx and approval portal | Only published TLS ports |
| Onyx | Model endpoint | Model requests | Allowlisted outbound HTTPS |
| Onyx | SupportPilot API | Registered business actions | Internal HTTPS; user token required |
| API | Keycloak | Keys and identity metadata | Internal HTTPS |
| API | OPA | Policy decisions | Private service network only |
| API | PostgreSQL | Authorized data access | Database port only; API role only |
| Approval portal | API | Review and approval | Internal HTTPS; approver token required |
| Worker | PostgreSQL | Claim jobs, store outcomes | Database port only; worker role only |
| Worker | Approved providers | Execute allowlisted effects | Destination and protocol allowlist |

Local implementation: four Docker networks — `edge`, `app`, `policy`, `data`
([08-local-build-runbook.md](08-local-build-runbook.md#3-step-1-repository-and-networks)).

## 9. Threat model

| Threat | Attack example | Primary controls |
|---|---|---|
| Direct prompt injection | "I am an administrator; ignore policy" | Identity from token; authorization outside model; deny by default |
| Indirect prompt injection | A ticket message tells the agent to export data | External data treated as data; narrow tools; per-call authorization; output limits |
| Cross-tenant access | User requests another tenant's order identifier | Trusted tenant context, API checks, RLS, minimal responses |
| Tool argument tampering | Model supplies a different organization or user id | Those fields are absent or ignored; server derives them |
| Excessive tool authority | Agent receives SQL, shell, or unrestricted HTTP | Only task-specific tools and destinations registered |
| Approval manipulation | Action changes after approval | Payload hash, immutable version, expiry, worker verification |
| Duplicate execution | Timeout causes the same refund to be retried | Idempotency key, unique constraint, atomic claim, provider reference |
| Credential exposure | Secret appears in prompt, log, or model output | Secrets mounted only to the required service; redaction; context minimization |
| Control-plane compromise | Runtime service changes tool registry or policy | Separate identities, network paths, credentials, review, deploy permissions |
| Resource exhaustion | Agent enters an expensive tool loop | Per-session limits, timeouts, quotas, circuit breakers, cost monitoring |

## 10. Failure behavior

| Failure | Required behavior |
|---|---|
| Keycloak unavailable | Existing valid tokens accepted only per configured key-cache policy; new authentication fails safely |
| OPA unavailable | **Protected operations are denied. No fallback allow rule.** |
| PostgreSQL unavailable | Controlled unavailable result; never fabricate business data |
| Model unavailable | No tool called without a model request; controlled service error |
| Worker unavailable | Approved jobs remain queued; the API does not execute them synchronously |
| Provider timeout | The worker checks provider state before retrying a possibly-completed operation |
| Audit write failure | Sensitive action transitions stop if evidence cannot be recorded transactionally |

## 11. Security decisions

| Decision | Reason |
|---|---|
| Onyx OpenAPI actions with individual OAuth identity | The action request preserves individual user permissions |
| OPA as a separate policy-decision service | Policy can be versioned, tested, reviewed, reused independently |
| PostgreSQL RLS as a second authorization layer | Tenant mistakes in application queries do not automatically expose every row |
| Separate API and worker | The user-facing path cannot directly perform protected effects |
| Separate runtime and migration database roles | Runtime compromise does not grant schema and policy administration |
| No generic SQL or HTTP tools | Business tools have smaller and testable authority |

## 12. References

- [Onyx OpenAPI Actions](https://docs.onyx.app/admins/actions/openapi)
- [Onyx Actions and Authentication](https://docs.onyx.app/overview/core_features/actions)
- [Open Policy Agent](https://www.openpolicyagent.org/docs)
- [Keycloak OpenID Connect](https://www.keycloak.org/securing-apps/oidc-layers)
- [PostgreSQL Row Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)
