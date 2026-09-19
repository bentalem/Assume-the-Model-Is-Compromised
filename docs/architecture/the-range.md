# The Range

The lab proves its controls to a machine. The Range proves them to a person.

It is a web application that arms the lab's own controls into broken states, lets a learner watch
what changes, shows the lab's source for why, and puts everything back. One rule shapes the product:
**the learner never opens a terminal.** If a challenge needs a command, the Range runs it.

```bash
docker compose --profile range up -d        # http://127.0.0.1:8095
```

Profile-gated, because a lab being used as a lab does not need it running.

---

## Why this service is the interesting one to review

To arm a challenge the Range must drop `FORCE` on a table, disable row security, and — later — stop
a container and install a different policy bundle. **That is more authority than anything else in
this repository holds**, and a service that can do all of it is precisely the control-plane
violation the lab spends eight tracks teaching people to find.

So it is bounded the way the lab would demand of anything else. Each of these is asserted somewhere,
not promised here.

| Boundary | Where it is enforced | What proves it |
|---|---|---|
| Owns nothing, reads no table | migration `0010` — `sp_range_role` has no grant in `app` | `permissions_smoke.sql`, `V-18` |
| Reach is a fixed function list | `EXECUTE` on named `SECURITY DEFINER` functions only | `permissions_smoke.sql` |
| Cannot reach the API or OPA | networks `edge`, `range_data`, `control` — never `app` or `data` | `V-17` |
| The model has no route to it | absent from `openapi/supportpilot-actions.*` | `V-19` |
| Never runs outside a local lab | `assert_local()` exits before binding a port | `services/range/tests/test_content.py` |
| Container control is three verbs | HAProxy allowlist, not the Docker socket | `infrastructure/local/docker-proxy/` |
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
small module in the package. The build brief says YAML; neither parser is vendored, and a repository
that teaches people to ask what a dependency can reach is a poor place to add one it does not need.
What the rule was protecting — content as data, adding a challenge means adding a file — is intact.

**Source is fetched, never copied.** Stage 03 reads the named line range out of the running stack at
request time, so the material cannot drift from the system it describes. The path never comes from a
request: pages render from the `SourceRef` objects the content declared at startup, and the container
sees four directories read-only (`database`, `services`, `policy`, `scripts`). Mounting the
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
| `python scripts/range_suite.py` | round trip per mutation, probe honesty against the catalogue, reset from an arbitrary armed set, flag unobtainable unarmed, refusal of undeclared ids |
| `python services/range/tests/test_content.py` | manifest validation, source references resolving, the local-only refusal |
| `python scripts/verify_local.py` | `V-17`–`V-19`, the Range's boundaries, skipped with a count when it is not running |

`range_suite.py` drives the service over HTTP rather than calling the registry in process. A registry
that works behind a console that cannot reach it is still a broken product.

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

---

## State

**Phases 0 and 1 are done, and Phase 2 is under way.** Four challenges are live, and between them
they exercise all three flag kinds and both halves of the console:

| | | Flag | Arms anything |
|---|---|---|---|
| 2.1 | The policy that filters nothing | `value` | two controls |
| 2.3 | Four questions | `value` | one, unnamed |
| 6.1 | Approve one payload, execute another | `reason` | one control |
| 6.2 | Self-approval, three times over | `value` | no — attempts a write that rolls back |
| 6.4 | The approval that outlived its payload | `reason` | one control |
| 7.3 | Prevented, or merely failed | `reason` | no — read-only |
| 7.4 | The test that lied in its own name | `written` | no — read-only |

Track 7 is read-only by design. Its subject is what the trail can and cannot show, and a challenge
that broke something first would be answering a different question.

6.2 is the one exception to observations being read-only: it *attempts* an approval, because the
subject of the challenge is what refuses the write. Both attempts undo themselves, neither takes an
argument, and the permitted case is deleted by hand — a challenge that silently approved a refund
the first time somebody pressed Run would not be a teaching tool. `range_suite.py` checks that
nothing is left behind.

A third finding, from 6.1 and the same family as the first two: `payload_binding` reported
"payload changed, hash did not" for any pending request whose amount was not 45.00 — including one
proposed at 1.00 that nothing had touched. A false positive in an investigative tool, which is worse
than a missing column: an indicator that fires on clean rows teaches people to ignore the indicator.
`0019` restricts it to the request the mutation acts on and renames the column to `matches_proposal`,
which is what it actually checks. Detecting tampering stays in the worker, which recomputes the hash —
and the challenge's own Stage 01 explains why the console must not try to do that job.

### What the remaining challenges need

Twelve `Ready` challenges remain, and they are not all the same kind of remaining.

**Blocked on Range-driven agent turns** (§5). 1.3, 3.1, 5.x and 8.1 all need the learner to make a
request *through the API*, which the Range deliberately cannot reach. That is the boundary working,
not a gap in it — the capability has to be built as its own reviewed change rather than by putting
the Range back on the `app` network. V-17 caught that exact shortcut once already.

**Blocked on seeded evidence.** 7.1 asks a learner to reconstruct a request from the audit trail,
and the trail on a fresh lab is empty: the rows that exist here now were produced by
`verify_local.py` and an afternoon's use. A challenge whose flag depends on whether somebody
happened to run the verification suite is a challenge that fails for the next learner, so 7.1 needs
a seeded evidence path — a fixed set of audit rows that ship with the lab — before it can be
written honestly.

That constraint is worth stating rather than working around. The alternative was a flag that
usually works.

**Ready to author now.** 1.1, 1.2, 1.4 and 6.3, which need no capability the Range does not have. Several of them — 1.3, 3.1, 5.x — need the
learner to make a request *through the API*, which the Range deliberately cannot reach. That is not
an oversight in the boundary; it is the "Range-driven agent turns" capability in
`.dev/ctf/design.md` §5, and it has to be built as its own reviewed change rather than by putting
the Range back on the `app` network.
