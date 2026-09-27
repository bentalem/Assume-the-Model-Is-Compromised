# The Range

The lab proves its controls to a machine. The Range proves them to a person.

It is a web application that arms the lab's own controls into broken states, lets a learner watch
what changes, shows the lab's source for why, and puts everything back. One rule shapes the product:
**the learner never opens a terminal.** If a challenge needs a command, the Range runs it.

```bash
docker compose --profile range up -d        # http://127.0.0.1:8095
```

Profile-gated, because a lab being used as a lab does not need it running.

Three pages, one vocabulary. `/` is the landing page: what this is, the tracks and what
each one establishes, and three named ways in — with the challenge count, this browser's solved
count and a live probe of the environment on it, because a landing page that reads "correct"
while the lab is armed would be the first lie the course tells. `/catalogue` is the index, a
table per track. `/guide` is the long version: the three stages and why they are in that order,
what the console sends, the three flag kinds, and where to start.

Every count and every track name on all three is generated at render time rather than written
down, so they cannot drift from what is loaded — and a test asserts the generation happened.

---

## Why this service is the interesting one to review

To arm a challenge the Range must drop `FORCE` on a table, disable row security, and — later — stop
a container and install a different policy bundle. **That is more authority than anything else in
this repository holds**, and a service that can do all of it is precisely the control-plane
violation the lab spends every track teaching people to find.

So it is bounded the way the lab would demand of anything else. Each of these is asserted somewhere,
not promised here.

| Boundary | Where it is enforced | What proves it |
|---|---|---|
| Owns nothing, reads no table | migration `0010` — `sp_range_role` has no grant in `app` | `permissions_smoke.sql`, `V-18` |
| Reach is a fixed function list | `EXECUTE` on named `SECURITY DEFINER` functions only | `permissions_smoke.sql` |
| Cannot reach the API or OPA | networks `edge`, `range_data`, `control` — never `app` or `data` | `V-17` |
| The model has no route to it | absent from `openapi/supportpilot-actions.*` | `V-19` |
| Never runs outside a local lab | `assert_local()` exits before binding a port | `services/range/tests/test_content.py` |
| Container control is three verbs on four names | HAProxy allowlist, not the Docker socket | `infrastructure/local/docker-proxy/` |
| Track 9: reach into memory-db is a fixed function list | `mem_range_role` owns nothing; `EXECUTE` on `range_mem.*` only | memory-db `permissions_smoke.sql`, `V-23` |
| Track 9: reads the vector store, never writes it | a read-only token per collection; no API key | `V-28` |
| Track 9: cannot reach the memory service or the model | `range_memory` only — never `memory_data` | `V-27` |
| Every action is evidence | writes `app.audit_events` as `actor_type='range'` | `scripts/range_suite.py` |

Two of these were not obvious and are worth stating plainly.

**The Range is not on `data`.** It was, in the first draft, because it needs PostgreSQL. `V-17`
failed immediately: the API is on `data` too, so sharing it handed the Range a route to the API.
The fix was a dedicated `range_data` network rather than a weaker check. This is the argument for
writing the boundary tests before the service has any authority to abuse — the check caught the
mistake while the worst consequence was a failing test.

**A result panel that shows another tenant's rows works because the function runs as the table
owner**, not because the Range can read across tenants. Revoke `EXECUTE` and the Range goes blind.
That is the same mechanism challenge 2.1 teaches, which is a happy accident rather than a design
goal, but it does mean the service cannot quietly grow a wider view without a reviewed migration.

---

## The probe service

Twelve challenges need a request made *through* the API, and the Range cannot reach the API (`V-17`).
The one-line fix — put the Range on the `app` network — would hand the service that can break every
control a route to the thing those controls protect. So a second service, `probe`, does it instead:

- It can reach the API — and, for track 9, the memory service, which is on the same `app`
  network — and it holds **one hand-written list of requests**. The Range asks for one by
  id; `probe` refuses any id that is not in its own registry. Nothing composes a request, and the
  list is the review surface — the same property that makes a parameterless `SECURITY DEFINER`
  function acceptable.
- It reports what a request *did* — status, error code, field names — never the values. Data a
  learner needs to read comes from an observation, where the row cap and the column list are
  enforced in the database.
- **Network placement does not make it one-way.** `probe` sits on `app` so that it can reach the
  API, and Docker networks are bidirectional, so anything else on `app` can open a socket to it.
  What makes the direction one-way is a **shared secret** mounted to exactly two services and
  compared in constant time. Reachable and usable are different properties; only the second is
  enforceable here, and `V-20` asserts that a request without the secret is refused.
- It holds one OAuth client credential and obtains tokens for the five seeded users, per request and
  not cached. Like the Range, it refuses to start unless `SUPPORTPILOT_ENV` is `local`.

The cost is that a new challenge in the identity, authorization, untrusted-content or control-plane
tracks usually needs a new probe, which is a code change rather than a content change. That is the
right trade: the alternative is a parameter that names a target, and the whole lab is an argument
against those.

---

## The mutation registry

Everything the Range can do to the lab is an entry in a server-side registry. **The browser sends an
id and nothing else.** There is no endpoint that accepts SQL, a role, a path, a container name or a
file — and the identifier is checked twice: against the registry, and against the ids the current
challenge declares. A real mutation that is not part of the open challenge is refused.

```python
Mutation(
    id="rls.orders.force_off",
    summary="Drop FORCE from app.orders",
    apply=lambda: db.call("arm_orders_force_off"),
    restore=lambda: db.call("restore_orders_force"),
    probe=_probe_force,
    touches=("app.orders",),
)
```

Four rules, each for a specific failure:

- **No mutation without an inverse.** The failure prevented is the worst one available here: a
  learner whose lab is quietly still armed an hour later, measuring a broken system and believing
  it is the real one.
- **The probe is the source of truth.** Armed or correct is read from the system on every render,
  never remembered. Arm something outside the Range and the console still tells the truth.
- **Reset asserts, it does not undo.** It walks every mutation, restores the ones whose probe is not
  `correct`, reports what it changed, and re-probes — raising if anything is still armed.
- **Observations are registry entries too.** Named, parameterless, fixed statement, declared row
  cap. There is no query box in this product and there will not be one: the lab's first rule is that
  the model never gets a generic tool, and the Range is held to the same standard.

On the SQL side the same principle repeats. There is no `set_row_security(table, enabled, forced)` —
a function with a target parameter is a generic tool wearing a business name, which is the finding
track 4 exists to teach. One function per mutation, the table written into the body.

---

## Content is data

A challenge is a directory, discovered and validated at startup. An invalid one is skipped with a
loud log line rather than crashing the service — and that log line has already earned its place:
`.dockerignore` excluded `**/*.md`, so the first image shipped manifests with no teaching material,
and the skip said so on the first boot.

```
content/02-tenant-isolation/01-policy-that-filters-nothing/
  challenge.toml      metadata, controls, observations, flag, source refs, hints
  stage-01/*.md       the learning tabs, in filename order
  stage-03/*.md       decision chain and review questions
```

**TOML rather than YAML**, read with the standard library's `tomllib`, and Markdown rendered by a
small module in the package. No YAML parser is vendored, and a repository that teaches people to
ask what a dependency can reach is a poor place to add one it does not need. Content stays data:
adding a challenge means adding a file.

**Source is fetched, never copied.** Stage 03 reads the named line range out of the running stack at
request time, so the material cannot drift from the system it describes. The path never comes from a
request: pages render from the `SourceRef` objects the content declared at startup, and the container
sees five directories read-only (`database`, `services`, `policy`, `scripts`, `openapi`). Mounting the
repository root would have handed the Range `.secrets/`.

### Flags

Three kinds — `value`, `reason`, `written` — declared per challenge. A `value` flag names an
observation and a column rather than carrying a literal, so **the answer lives in the seed data and
the Range asks the database for it.**

The property that matters is not secrecy; there is no scoreboard and nobody to cheat. It is that
**the flag must be unobtainable while every mutation probes `correct`**, and that is tested. The
first version of challenge 2.1 failed exactly this: an owner-side policy of `USING (true)` made the
flag readable before anything was armed, which would have made the challenge solvable by pressing a
button. Migration `0013` fixed the policy rather than the test.

---

## Testing

| Suite | Covers |
|---|---|
| `python scripts/range_suite.py` | round trip for **every registered mutation**, read from the service's own `/registry`; probe honesty against the catalogue; reset from an arbitrary armed set; flag unobtainable unarmed; refusal of undeclared ids; and the state the suite leaves behind |
| `python services/range/tests/test_content.py` | manifest validation, source references resolving, the local-only refusal |
| `python scripts/verify_local.py` | `V-17`–`V-21`, the Range's boundaries, and `V-22`–`V-31` for the memory stack, each skipped with a count when its profile is not running |

`range_suite.py` drives the service over HTTP rather than calling the registry in process. A registry
that works behind a console that cannot reach it is still a broken product.

---

## Track 9: the memory stack

Track 9's controls live in a second database. The arrangement is the same one, applied again:
`mem_range_role` owns nothing and may `EXECUTE` only the functions in the `range_mem` schema
(memory-db migrations `0006`, `0008`, `0009`, `0010`), each `SECURITY DEFINER`, bounded, and
returning named columns. The Range reads Qdrant with a read-only token per collection and never
holds its API key.

### Eight settings, one function

Every track 9 mutation is a row in `mem.settings`, flipped by `range_mem.set_setting` — which accepts
a key and a value, checks both against fixed lists, and writes an audit event in the same
transaction. The browser can name a setting; it cannot invent one.

| Mutation | Setting | Secure → armed | Challenge |
|---|---|---|---|
| `memory.write.secret_filter_off` | `write.secret_filter` | `on` → `off` | 9.1 |
| `memory.context.provenance_off` | `context.provenance` | `on` → `off` | 9.2 |
| `memory.history.org_readable` | `history.org_readable` | `false` → `true` | 9.3 |
| `memory.history.revalidate_off` | `history.revalidate` | `on` → `off` | 9.4 |
| `memory.write.auto_confirm` | `write.auto_confirm` | `false` → `true` | 9.5 |
| `memory.store.shared_collection` | `store.layout` | `per_tenant` → `shared` | 9.6 |
| `memory.rules.self_activate` | `rules.self_activate` | `false` → `true` | 9.7 |
| `memory.forget.primary_only` | `forget.scope` | `all` → `primary` | 9.8 |

The service reads settings per request, so nothing restarts. The probe reads `setting_state` in a
**separate call** from any `set_setting`: read in the statement that changed it, a setting still
shows its old value, and an early version reported an armed switch as correct for exactly that
reason.

### Restoring a switch is not recovery

Three settings let something through that outlives them: a memory born confirmed (9.5), a rule that
activated itself (9.7), a summary that survived its source's forget (9.8). Putting the switch back
closes the hole and does nothing about what already came through it — so for these three the probe
also asks `range_mem.leftovers()`, and reports `correct` only when the setting is secure **and**
nothing it let through remains. The restores do the second half: send auto-confirmed memories back to
unconfirmed, retire rules nobody approved, and re-run `memory-init` through the proxy to complete
half-done forgets. Each writes an audit event per row. None of them can touch what a person did — a
rule someone approved, a memory someone confirmed — and the store's own policies say so, not only
the `WHERE` clauses.

The 9.8 restore waits for **that run** of `memory-init` to exit 0. A one-shot container is `exited`
before it starts as well as after, so waiting for the state alone would report a repair that never
ran. That exact failure happened once: the proxy was still running an allowlist from before
`memory-init` was added, refused the start with a 403, and the switch went back while the repair did
not. `range_suite.py` now fails a round trip whose console reports the restore failed, even if the
probe reads correct.

### Observations run a scenario, then read the log

A memory challenge is rarely one request — "a tool result reaches the model" is a turn written, then a
context block assembled. So the probe service gained **scenarios**: fixed sequences, each step a
literal method, path and body in its registry. The one thing that moves between steps is a value an
earlier step's response returned (a new session's id, a memory's id, the email the API showed bob),
substituted into the parsed body as a JSON string or into the path percent-encoded — so it can fill a
field or a segment and never change the request's shape.

The flag observations run their scenario first and then read what the memory service logged —
`mem.context_log` for every context block, written in the same transaction as its audit event. That
makes each one a measurement of the system as it is now: arm a control, run it, and the value
appears; restore, run it again, and it does not. It is also why a flag check re-runs the scenario,
and why 9.8's observation looks at alice's last three forgets rather than one.

Every flag column is computed in memory-db from the evidence, so a value appears only in the state the
challenge is about — a credential only if one was *included* in a block, an email only on a turn the
log marks as having outlived its permission. 9.4 needs two controls armed, and `range_suite.py`
proves the flag is unobtainable with either one alone.

### Absent is a state

The memory stack is a compose profile. When it is not running, memory-db cannot be reached and its
eight controls read **`absent`** — never `correct`, and not `unknown` either, because the Range knows
exactly why it cannot read them. The banner leaves them out of its count and says how many; reset
skips them, because there is nothing running to restore; `range_suite.py` skips track 9 and says so.

### The dual-write artifact

The memory service writes every memory to **both** vector layouts — its tenant's collection and the
shared one — so that arming 9.6 needs no re-indexing. A real deployment would write one layout. It is a
lab artifact, and it is the reason 9.6's observation reads the layout the setting selects rather than
whatever happens to exist: the shared collection is always populated, and what 9.6 measures is what
the service's query reaches when that is the layout it uses.

---

## Two findings from building it, worth keeping

**An observation that under-reported the worse failure.** `catalogue.unforced` asked for tables that
were *enabled but not forced*. A table with row security disabled entirely does not match that, so
while `app.orders` sat at `enabled=false, forced=false` the audit view returned **nothing** — the
most reassuring possible answer to the worst possible state. It was caught because the migration
job's smoke test refused to run and named the table while this observation said there was nothing
to report: two instruments disagreed, and the stricter one was right. Fixed in `0015`.

**Nothing noticed that the lab had been left armed.** Two controls stayed armed across a session and
the first thing to complain was a migration job, half an hour later. A service whose entire job is
arming controls should be the first to report that it left some armed, not the last. The Range now
probes on startup and says so, and `range_suite.py` asks the database directly what state it is
leaving behind rather than trusting its own reset call.

The second one is the more useful lesson, and it is the lab's own: *a control that is configured is
not a control that is running.* Reset was implemented, tested, and reported success — and the thing
that actually proved it was asking the database afterwards.
