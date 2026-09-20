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
| 5.2 | Indirect, and why it is a finding | `written` | no — the corpus is seed data |
| 6.1 | Approve one payload, execute another | `reason` | one control |
| 6.2 | Self-approval, three times over | `value` | no — attempts a write that rolls back |
| 6.3 | Exactly once | `value` | no — attempts a write that rolls back |
| 6.4 | The approval that outlived its payload | `reason` | one control |
| 1.1 | Whose token is it | `value` | configures a service account |
| 1.2 | A token for another service | `written` | no — a genuine token for the wrong door |
| 1.3 | Roles come from the database | `written` | one control, then a real API request |
| 1.4 | The claim that changes nothing | `value` | no — three tampered tokens |
| 3.1 | Deny by default, proved | `reason` | stops the policy engine |
| 3.2 | Yes, and only these fields | `written` | no — two real API requests |
| 3.3 | Which layer stops what | `written` | two controls, both on the live policy |
| 4.1 | The worst legal call | `written` | no — the authority is in the schema |
| 7.1 | Reconstruct it | `written` | no — read-only |
| 7.3 | Prevented, or merely failed | `reason` | no — read-only |
| 7.4 | The test that lied in its own name | `written` | no — read-only |

Track 7 is read-only by design. Its subject is what the trail can and cannot show, and a challenge
that broke something first would be answering a different question.

7.1 turned up a property of the audit table that is worth recording here rather than only in the
challenge, because it is a fact about the lab and not only teaching material.

`app.audit_events` declares `trace_id`, `previous_event_hash` and `event_hash`. All three are empty
in every row the system has ever written: the API's INSERT does not name the two hash columns at
all, and nothing supplies a trace id. **The trail is append-only but not tamper-evident**, and the
append-only half is enforced twice — no runtime role holds `UPDATE` or `DELETE` on the table, and
the owner, which does hold them, is stopped by `FORCE ROW LEVEL SECURITY` with no policy for either
command. An owner's `UPDATE` therefore returns `UPDATE 0` rather than an error, which is worth
knowing before reading it as success.

This is not being fixed by adding a hash chain today. It is written down because the gap between a
declared column and a written one is exactly what 7.1 teaches learners to look for, and a repository
making that argument should state where it has one of its own. `range.audit_column_use()` reports
the counts, so the claim is a query rather than a paragraph that was true when it was typed.

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

Eighteen of the thirty-one rows in `.dev/ctf/design.md` are built. Thirteen are not, and they are
not all the same kind of not-built. Three of them the design marks `Ready`, and the honest position
on each has changed now that the Range exists to test the assumption against.

**Blocked on a model in the loop.** 4.3, 5.1, 5.3 and 7.2 need a conversation, not an HTTP request.
The probe service makes requests; it cannot be steered by text it reads, which is the entire subject
of those four. That means driving Onyx, a separate compose project and its own decision.

5.1 carries a second problem worth recording before anyone builds it. Its stated outcome is *"two
identical refusals"* — an assertion about what the model did. `CLAUDE.md` forbids exactly that, and
for a good reason: two identical runs produce different tool calls. If 5.1 is built, the flag has to
be about the boundary around the model, never about the model's answer.

**3.3 is built, and it is not the challenge the design describes.** The design has it install a
permissive policy and the learner discover that row-level security refuses anyway. Building it
turned up something better and more uncomfortable: for a cross-tenant order read, *the policy is
never consulted at all*. The API loads the trusted resource before it builds the policy input, so a
read the database will not satisfy is refused at the load with `resource_not_visible` and no policy
version. Arming a permissive tenant rule changes nothing — not the response, not the audit row.

So the challenge as shipped removes two different conditions from the same action and asks why the
results differ. Removing the tenant check does nothing, because a second layer was already holding
that property up. Removing the role check returns order data to a `finance_approver`, because
nothing underneath the policy has an opinion about roles. The lesson is sharper than "we have two
layers": **one property has two layers and the rest have one**, and the severity of a policy bug is
decided by which of those you are looking at.

The mechanism is worth recording because the obvious one does not work. `decision` is a complete
rule with many definitions, so an overlay file asserting it produces a conflict, OPA errors, and the
API denies — which reproduces challenge 3.1 and teaches nothing. The bundle has to be replaced
wholesale. It is therefore a named volume, populated from `./policy/supportpilot` by
`opa-bundle-init` on every `compose up`, never the working tree: a mutation that wrote to the
working tree could leave a crashed container's permissive authorization policy checked out in a git
clone, and "no mutation without a proven inverse" stops being true the moment the inverse depends on
the container still being alive.

The permissive policy is **derived, never stored**. There is no wrong `.rego` file in this
repository or in the Range image. Arming reads the real policy from the read-only mount and removes
one named condition, asserting first that the text it expects is present — so the armed policy is
always the real one minus one control, and editing the policy makes arming fail loudly rather than
arm something stale. Against the correct bundle the policy suite is 53/53; against the permissive
one exactly two tests fail, named for the control that was removed.

`range_suite.py` asserts both outcomes, including the containment half: no order crosses a tenant
boundary while the policy permits it. "A permissive policy is safe here because the database
refuses" is precisely the kind of sentence that has to be measured rather than believed.

**8.1 is still not Ready.** It turns on the published action document drifting from the registered
code, which means arming a change to a file in the repository, with the same un-guaranteed inverse
that the policy bundle avoided by being a volume. The acceptable shape is the same one: put the
drifting copy somewhere that is not the working tree. It has not been built.

**Blocked on capability the design already names.** 2.2, 3.4, 4.2, 4.4, 5.4, 8.2, 8.3 and 8.4 each
need something that does not exist. 2.2 and 3.4 are refused outright by ADR-0004. The rest are
ordinary unbuilt work: an outbound tool, an unschema'd `object` parameter, a URL-taking tool, an
MCP-style tool source, a prompt store.

**Resolved.** 7.1 was blocked on seeded evidence — the trail on a fresh lab is empty, and a flag
that depends on whether somebody happened to run the verification suite is a flag that fails for the
next learner. `database/seeds/0004_completed_refund.sql` now ships one completed refund as fixture
history: the action request, its approval, its job, its execution evidence and its four audit rows,
all consistent, with a payload hash that is the real sha256 of the canonical payload. The separation
of duty trigger accepts it because alice proposes and fiona approves — a fixture that tried to seed
a self-approval fails the seed file rather than producing a trail the system could never have
written.
