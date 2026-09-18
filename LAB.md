# The SupportPilot lab

A working multi-tenant AI support agent you can install, attack, and take apart.

It is a real system, not a mock: Onyx runs the agent loop, Keycloak issues the identities,
a FastAPI service exposes seven tools, Open Policy Agent decides, PostgreSQL enforces row-level
security, and a separate worker is the only component that can move money.

> **The core rule:** the model may *propose* tool use. Trusted services decide what is allowed, and
> trusted services perform every real action.

The article this lab was built for is [`README.md`](README.md). Read it first if you have not — it
explains *why* each control is where it is. This file gets the system running so you can break it.

---

## 1 · Before you start

| You need | Why | Check |
|---|---|---|
| Docker Desktop or Docker Engine, with Compose v2 | Nine containers | `docker compose version` prints v2 |
| At least 8 GB of memory available to Docker | Keycloak and PostgreSQL are the heavy ones | Docker Desktop → Settings → Resources |
| About 20 GB of free disk | Images and volumes | `docker system df` |
| Python 3.11 or newer, on the host | Every script here is Python | `python --version` |
| `httpx` for the host scripts | The suites talk to the stack | `pip install httpx` |

Windows, macOS and Linux all work. The commands below are written once; on Windows use PowerShell,
everywhere else use your usual shell. Where a `.ps1` wrapper exists it only calls the Python script,
so `python scripts/<name>.py` is always the portable form.

> **Safety.** This environment holds invented records only. Never point it at real customer data,
> never load a production dump, and never give it a real payment credential. Everything in it is
> designed to be attacked, including by you.

---

## 2 · Install

```bash
git clone https://github.com/bentalem/Assume-the-Model-Is-Compromised
cd Assume-the-Model-Is-Compromised

python scripts/bootstrap_local.py
```

The bootstrap generates local secrets into `.secrets/` if they are missing, builds the images, starts
the stack, applies the migrations, and waits for Keycloak's realm and the API to come up. The first
run pulls images and takes several minutes. It is safe to re-run: existing secrets are left alone, so
the database keeps working.

Useful flags:

| Flag | Effect |
|---|---|
| `--reset` | Destroy the volumes first. The database is rebuilt from migrations and seeds. |
| `--rebuild` | Rebuild images without the layer cache. |
| `--with-onyx` | Also start Onyx (see section 7). |

When it finishes it prints where things are. Then prove the environment is actually correct:

```bash
python scripts/verify_local.py
```

Sixteen checks, `V-01` through `V-16`, one line each. **Every one must pass.** A bootstrap that
succeeded is not the same as an environment that is correct — `verify_local.py` is what tells you
which.

If a check fails, jump to section 8.

---

## 3 · What you now have

| Where | What |
|---|---|
| `https://localhost:8443` | Keycloak, realm `supportpilot`. Self-signed certificate — your browser will warn. |
| `http://localhost:8080` | The same Keycloak over plain HTTP, for the test harness. |
| `http://localhost:8090` | The approval portal. |
| — | The API has **no published port**. That is deliberate: it is reachable only from inside the `app` network, so every request has to arrive the way a real one does. |

### The people

Five accounts, two tenants that must never see each other. The passwords are in the realm export and
are throwaway values for a throwaway realm.

| User | Tenant | Role | Password |
|---|---|---|---|
| `alice` | Cedar | `support_agent` | `alice-local-password` |
| `bob` | Cedar | `support_manager` | `bob-local-password` |
| `fiona` | Cedar | `finance_approver` | `fiona-local-password` |
| `dana` | Cedar | `auditor` | `dana-local-password` |
| `mallory` | Northwind | `support_agent` | `mallory-local-password` |

### The data

| | Cedar | Northwind |
|---|---|---|
| Orders | `ORD-2001` · `ORD-2002` · `ORD-2003` | `ORD-3001` |
| Customers | `CUS-4001` · `CUS-4002` · `CUS-4003` *(restricted)* | `CUS-9001` |
| Tickets | `TKT-1001` *(carries ten injections)* | `TKT-3001` |

Three of these carry most of the lessons:

- **`ORD-3001`** belongs to Northwind. Alice must never read it, however she asks.
- **`CUS-4003`** is marked `restricted`. An agent gets the record *without* the email address; a
  manager gets it with. The address is not hidden from the agent — it never reaches the agent.
- **`TKT-1001`** contains ten injection attempts written to look like ordinary customer messages.

The architecture, with diagrams: [`docs/architecture/`](docs/architecture/).

---

## 4 · Your first ten minutes

Do these three in order. They are the shortest path to understanding what the lab is for.

**See a token become a subject.**

```bash
python scripts/learn_identity.py token
```

It signs in as alice and prints every claim in her access token. Then:

```bash
python scripts/learn_identity.py forge
```

It tampers with a claim — changing her organization — and sends it. Watch the API refuse. The tenant
does not come from the token's claims; it comes from the database, keyed by the verified subject.

**Watch a control fail.**

```bash
python scripts/learn_authorization.py outage
```

It stops OPA mid-flight and repeats a request alice is *fully entitled* to make. You should get `503`
and no data. There is no cached allow and no local fallback. If you ever see the order come back,
something has a fallback somebody forgot to mention.

**Watch a control that is present and doing nothing.**

```bash
python scripts/learn_rls_ownership.py
```

PostgreSQL exempts a table's **owner** from its own row policies unless `FORCE` is also set. An
application connecting as the role that ran the migrations therefore gets no filtering at all —
while the policies sit in the schema, correctly written, present in every dump. Nothing in a code
review shows this.

That third one is the single most useful thing in this repository. It is a real finding, it survives
review, and it has nothing to do with AI.

---

## 5 · The practice track

Each script is a module. They are independent; run them in any order, but this order builds.

### Identity — whose token is on the call?

```bash
python scripts/learn_identity.py token        # decode alice's token, every claim
python scripts/learn_identity.py forge        # tamper with a claim, watch the refusal
python scripts/learn_identity.py audience     # a valid token for the wrong service
python scripts/learn_identity.py demote bob   # take bob's manager role away, live
```

`demote` is the one to sit with. Roles are loaded from the database on every request, so removing a
membership takes effect on the next call — no token reissue, no cache to wait out.

### Service accounts — what the easy wiring costs

```bash
python scripts/learn_service_account.py build
```

This builds a second agent wired the common way: one credential for every user. Then ask it, as a
Cedar user, for `ORD-3001`. Same model, same prompt, same tools, same policy — one header value
different, and the tenant boundary is gone.

There is a written walkthrough for this one:
[`docs/learning/exercise-02-whose-token.md`](docs/learning/exercise-02-whose-token.md). Allow twenty
minutes; the comparison table is the point.

### Authorization — policy as code

```bash
python scripts/learn_authorization.py input     # the exact input and decision, from OPA's log
python scripts/learn_authorization.py matrix    # every user against every resource, as a grid
python scripts/learn_authorization.py fields    # obligations: the same record, two roles
python scripts/learn_authorization.py outage    # stop OPA mid-flight
python scripts/learn_authorization.py break     # install a policy that allows cross-tenant reads
python scripts/learn_authorization.py restore   # put the real policy back
```

`break` then `restore` is the exercise. Install the bad policy, confirm the cross-tenant read now
succeeds at the policy layer — and then notice that the *database* still refuses it. Two layers is
not a slogan.

### Tenant isolation — the failure that passes review

```bash
python scripts/learn_rls_ownership.py
```

Afterwards, you have four questions to ask any team that says they use row-level security: which role
does the application connect as, does that role own the tables, is `FORCE` set, and does the role
hold `BYPASSRLS`. One catalogue query answers all four, and you do not need access to their
application to run it.

---

## 6 · Where to start breaking it

Beyond the scripted modules, these are worth doing by hand. Roughly in order of how much each one
teaches.

1. **Stop OPA**, then read an order you are entitled to read. `503`, no data, no partial answer.
2. **Point the API at the migration role** instead of `sp_api_role` and read across tenants.
3. **Drop `FORCE`** from one table's row-level security and try again.
4. **Ask the agent for fifteen customer searches in one message.** Every call will be authenticated,
   authorised, correctly tenant-scoped and correctly logged — and you will have the directory. This
   is the opening of the article, and there is no injection anywhere in it.
5. **Approve a refund, then change the amount** in the database before the worker claims it. The hash
   check should refuse it twice over — against the stored hash and against the approved one.
6. **Give the agent a service-account token** instead of the user's own, then ask as alice for
   `ORD-3001`.

When something does not happen, always establish **whether it was prevented or whether it merely
failed**. A malformed request that never reached the authorization pipeline is not evidence that
authorization worked.

---

## 7 · Optional — putting a real model in the loop

Everything above works without Onyx, which is deliberate: the enforcement boundary is
API → OPA → PostgreSQL, and every control can be proven with no model in the loop.

Add Onyx when you want to see an agent choose the tool calls itself — which is what the abuse suite's
two skipped cases need, and what makes the fifteen-search extraction feel real.

```bash
python scripts/enable_keycloak_tls.py     # Onyx refuses a plain-HTTP identity provider
python scripts/bootstrap_local.py --with-onyx
python scripts/connect_onyx.py            # joins the networks, configures the client
python scripts/verify_onyx_flow.py        # checks the chain link by link
```

Two steps cannot be automated and `connect_onyx.py` prints the exact values for them: registering the
action document in Onyx's admin UI, and turning on **"Pass through user's OAuth token"**. There is a
hosts-file line as well.

The full procedure, including a troubleshooting table:
[`docs/runbooks/onyx-integration.md`](docs/runbooks/onyx-integration.md).

---

## 8 · Proving it works, and what to do when it does not

| Command | What it proves |
|---|---|
| `python scripts/verify_local.py` | 16 environment checks, `V-01` to `V-16` |
| `python scripts/abuse_suite.py` | injection and abuse cases — two need Onyx and skip without it |
| `python scripts/action_suite.py` | approval and execution: no self-approval, no double execution |
| `python scripts/contract_suite.py` | every call built from the published tool document |
| `opa test policy/` | the policy rules, including every deny arm |
| `pytest services/api` | token verification, policy client, pipeline, hashing, pagination |

### When something is wrong

**Start with the logs.** `docker compose ps` shows what is running; `docker compose logs --tail 100 api`
(or `keycloak`, `opa`, `worker`, `migrate`) shows why something is not.

| Symptom | Usually |
|---|---|
| Bootstrap hangs waiting for the migration job | Docker has too little memory. Raise it to 8 GB and `--reset`. |
| Bootstrap hangs waiting for the Keycloak realm | Keycloak is slow on a first start. Give it a few minutes, then check its logs. |
| `V-01` fails | A container is not running. `docker compose ps`, then read that container's logs. |
| A check fails after you changed something | That is the lab working. Find out which layer changed before you change anything back. |
| Everything is confusing | `python scripts/bootstrap_local.py --reset` returns you to a known state. |

**Never fix a failing check by weakening a control.** Disabling row-level security, granting a
bypass, or relaxing a token check to make something work invalidates every result you produce
afterwards. [`CLAUDE.md`](CLAUDE.md) lists the nine shortcuts that are never acceptable.

---

## 9 · Where things are

```
README.md                 the article
LAB.md                    this file
CLAUDE.md                 the invariants — what must never be weakened
compose.yaml              four networks, nine services
services/
  api/                    auth · policy · tools · repositories · audit
  worker/                 jobs · adapters · idempotency
  approval-portal/        renders a payload hash, forwards a decision
database/
  migrations/             schema, roles, grants, RLS — owned by sp_migrator_role
  seeds/                  the two tenants and the injection corpus
policy/supportpilot/      authz.rego + limits.json
policy/tests/             the policy tests
openapi/                  the registered action set, for Onyx
infrastructure/local/     Keycloak realm, Onyx compose overlay
scripts/                  bootstrap, verify, the suites, the learning modules
docs/
  architecture/           how it fits together, with diagrams
  learning/               the training track and the field manual
  runbooks/               connecting Onyx · investigating an incident
specs/                    the exact contracts: schema, API, policy
```

Start with [`docs/architecture/`](docs/architecture/) to understand the system, and
[`docs/learning/00-curriculum.md`](docs/learning/00-curriculum.md) to work through it as a course.

---

## 10 · What this lab is not

No autonomous refunds without approval. No free-form SQL from the model. No general shell,
file-system or cloud-administration tool. No model training. And no production deployment — this is
Compose on one machine, holding invented data, built to be attacked.
