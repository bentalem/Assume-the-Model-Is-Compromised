# The Range

The lab proves its controls to a machine. The Range proves them to a person.

It is a web application that arms the lab's own controls into broken states, lets a learner watch
what changes, shows the lab's source for why, and puts everything back. One rule shapes the product:
**the learner never opens a terminal.** If a challenge needs a command, the Range runs it.

```bash
docker compose --profile range up -d        # http://127.0.0.1:8095
```

Profile-gated, because a lab being used as a lab does not need it running.

Three pages, one vocabulary. `/` is the landing page: what this is, the eight tracks and what
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

**All thirty-one challenges in `.dev/ctf/design.md` are built.** They exercise all three flag kinds
and both halves of the console:

| | | Flag | Arms anything |
|---|---|---|---|
| 1.1 | Whose token is it | `value` | one control |
| 1.2 | A token for another service | `written` | no |
| 1.3 | Roles come from the database | `written` | one control |
| 1.4 | The claim that changes nothing | `value` | no |
| 2.1 | The policy that filters nothing | `value` | 2 controls |
| 2.2 | The word LOCAL | `written` | no |
| 2.3 | Four questions | `value` | one control |
| 3.1 | Deny by default, proved | `reason` | one control |
| 3.2 | Yes, and only these fields | `written` | no |
| 3.3 | Which layer stops what | `written` | 2 controls |
| 3.4 | The failure that looks like consent | `reason` | 3 controls |
| 4.1 | The worst legal call | `written` | no |
| 4.2 | The generic tool wearing a business name | `written` | no |
| 4.3 | Inside every limit | `value` | no |
| 4.4 | Bounded recipient, unbounded content | `written` | no |
| 5.1 | Direct, and why it is not a finding | `written` | no |
| 5.2 | Indirect, and why it is a finding | `written` | no |
| 5.3 | Second order | `written` | no |
| 5.4 | The output is input too | `written` | no |
| 6.1 | Approve one payload, execute another | `reason` | one control |
| 6.2 | Self-approval, three times over | `value` | no |
| 6.3 | Exactly once | `value` | no |
| 6.4 | The approval that outlived its payload | `reason` | one control |
| 7.1 | Reconstruct it | `written` | no |
| 7.2 | What the response said | `written` | one control |
| 7.3 | Prevented, or merely failed | `reason` | no |
| 7.4 | The test that lied in its own name | `written` | no |
| 8.1 | The third copy | `written` | no |
| 8.2 | Where can it reach | `written` | no |
| 8.3 | A tool server changes its mind | `written` | no |
| 8.4 | The text nobody approved | `written` | no |

`range_suite.py` also runs **every observation every challenge declares**, on every challenge. The
content tests prove a challenge renders and that its control ids resolve; they never call an
observation, so a renamed SQL function or a dropped column would pass every test and fail the first
learner who pressed Run. Every one of them, checked against the console's own `ran` line rather
than against the word "failed" — 7.4 renders a source panel containing that string, and the first
version of this check reported it as a broken observation. There is no count in this sentence on
purpose: the one that used to be here was wrong within two challenges of being written.

The same suite now proves the **flag integrity rule** — *a flag must be unobtainable while every
mutation probes correct* — for every challenge that owes it, rather than for one challenge against a
hardcoded value. Three challenges have a value flag and a control to earn it: 1.1, 2.1 and 2.3.

The answer is discovered rather than written down next to the check. The observation is read with
the environment correct, read again with the challenge's controls armed, and the flag is taken from
the **difference** between the two result sets. That definition matters: the first version of this
check took the first value in the column and picked a cedar order's amount out of 2.1 — a row that
is visible whether or not anything is armed — then reported the challenge as broken when the flag
was still accepted afterwards. What makes a flag earned is that it is in the armed result set and
not in the correct one. Asking for the difference finds 2.1's real answer on its own, and it is the
value the older hardcoded check asserts.

A value flag on a read-only challenge carries no such obligation, and the console already says so
rather than claiming the answer was unreachable a minute ago.

One observation is empty while the environment is correct, and that is the designed answer rather
than a fault: `catalogue.unforced` lists the tables that are not fully protected, and 2.3 exists
because the list is empty until something is armed. The suite names the expected empty one, so a
second one appearing gets a second look instead of being absorbed.

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

The append-only half is now a query as well. `range.audit_write_access()` reads the table's ACL and
its policies out of the catalogue and returns one row per command: who holds the grant, which
policy would match, and what a statement therefore does. It reports `TRUNCATE` alongside the other
four, because row-level security does not filter a table-level command — the owner holds it and no
policy stands between it and the record, which is the concrete form of "append-only is made of
grants".

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

### How the eleven hard ones were built

All thirty-one rows of `.dev/ctf/design.md` are built. Eleven of them were, at various points,
recorded in this document as blocked — five by a rule, four by needing a model, two by needing the
Range to write the repository working tree. None of those obstacles was wrong. What changed is that
the design's *stated mechanism* turned out not to be the only way to reach its *stated lesson*, and
the pattern that got each one built is worth recording, because the next person will meet it too.

**The pattern.** When the design asked for a capability this lab must not have, the question that
unlocked it was never "how do we add this safely". It was: **where does this property already exist
in the system as built?** Every time, it did.

| | The design asked for | What it was built on instead |
|---|---|---|
| 2.2 | a togglable request-context mode | the word `LOCAL`, and the check that would fail without it |
| 3.3 | a permissive policy revealing RLS underneath | the policy is never consulted for that read — so the lesson became which layer covers what |
| 3.4 | a deliberately wrong fallback mode | three ways to break the engine that all deny, and are not equally visible |
| 4.2 | a deliberately bad tool | the checker, which has no rule for the shape it describes |
| 4.3 | session budgets, and a way to drive the agent | two permitted searches and the cursor between them |
| 4.4 | an outbound tool | the absence of one, and what would have to exist first |
| 5.1 | two refusals from a model | the ceiling: a direct injection's author is the caller |
| 5.3 | a seeded second-order path | a seeded note, and the honest fact that the loop is not closed |
| 5.4 | a rendering surface | the approval portal, which a human reads and which does escape |
| 7.2 | an agent transcript that lied | a true response and a truer record, disagreeing |
| 8.1 | the document drifting from the code | the third copy, which a person pastes into a form |
| 8.2 | a URL-taking tool | the network map, and what would have answered |
| 8.3 | an MCP-style tool source | static registration, and what an ADR would have to decide first |

**Nothing was weakened to get there.** No fallback-allow path, no generic tool, no URL-taking tool,
no egress, no togglable context mode. The API has exactly the behaviour it had before this work
started, and `verify_local.py` proves it on every run.

**Three were built by measuring rather than arguing**, and each one contradicted a premise this
document had previously asserted:

  * 3.3 was designed around a permissive policy revealing row-level security underneath. Arming it
    changed nothing observable, because the API loads the trusted resource before it builds the
    policy input, so a cross-tenant read never reaches OPA at all.
  * 5.3 was briefed on the basis that the second-order loop was already seeded. The note exists;
    the loop does not. `add_internal_note` writes `app.internal_notes` and `get_ticket` reads
    `app.ticket_messages`, and nothing reads the former back.
  * 5.4 was expected to find an unescaped rendering surface. The approval portal escapes everything,
    through `html.escape` with its `quote=True` default. Its test directory is empty, which is the
    finding the challenge ends on.

**What is still deferred, and it is not a challenge.** 8.3 ships as a design exercise and says so.
Building the thing it describes — a tool source that alters its list at runtime — needs an ADR
first, because rule 10 says external text cannot register tools and a runtime tool source is
exactly a component that does. The challenge names the six questions that ADR would have to answer.

**A note on reading `.dev/ctf/design.md` now.** It is the original specification and has
deliberately not been amended. Its §5 lists capabilities to grow that were never grown, and two of
them must not be: a deliberately wrong policy-fallback mode, which ADR-0004 refused and `CLAUDE.md`
prohibits, and a URL-taking tool, which rule 7 names directly. The design document is the question.
This section is the answer, and where they disagree, this one is later.
