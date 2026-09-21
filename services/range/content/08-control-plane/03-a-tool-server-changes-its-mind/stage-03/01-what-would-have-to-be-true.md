# What would have to be true

## The moment the list is decided

Three artefacts, and all three are files somebody merged:

| Artefact | What it fixes | When |
|---|---|---|
| `create_app` in the API | which routers exist at all | process start, from the image |
| `APPROVED_OPERATIONS` in the export script | which operation ids may appear in the document | at export, before the file is written |
| `openapi/supportpilot-actions.json` | the list Onyx is given | when somebody commits the regenerated file |

Change any one of them without the others and the export fails rather than producing a document.
An unapproved operation is a finding; an approved operation that has disappeared is also a finding;
and the script writes nothing at all while either is true. That is the closed loop, and its property
is worth naming exactly: **the registered set cannot change without a diff.**

Not "should not". Cannot — there is no path from a running process to that list.

## What a runtime tool source changes

Two things, and they fail differently.

| | What moves | Which control in this lab covers it today |
|---|---|---|
| The set | a tool exists that no diff ever showed | none — every control here is a control over requests |
| The text | third-party prose enters the model's instruction context | none — and 8.4 is the challenge about that for your own prose |

That second column is the uncomfortable part, and it is the same answer 8.4 arrives at from the
other direction. Approval, payload hashing, idempotency, audit, row-level security and the policy
engine are all controls on **a request that has already been made**. A tool list is not a request.
Nobody proposes it, so nothing approves it; there is no transaction, so rule 9's audit-in-the-same-
transaction has nothing to attach to.

The one check that is about the tool set — the export — runs against code in the image, on a
developer's machine or in CI, before anything is deployed. It cannot see a list that arrives at
connection time, and it would not be wrong to say so: it is a consistency check between two
artefacts you control, and a third party is not one of them.

## What holds anyway, and why that is the interesting half

Read the policy client panel. The authorization input is four members: subject, action, resource,
context. A description is not one of them, and nothing further down reads one. Neither does
row-level security, which is a `USING` clause on a table, nor the separation-of-duty trigger, which
compares two identities.

So a description can change what an agent **attempts**. It cannot change what the API permits.

That distinction is the whole reason this is a tractable problem rather than a hopeless one, and it
is worth being precise about rather than reassuring. It does not mean a malicious description is
harmless:

- A tool that exists at all is a surface, and the second tool in the Stage 01 example is the finding, not the sentence that mentions it.
- Requests that are refused still happen, and a flood of them looks, in your logs, exactly like an incident you did not have.
- The description is also read by people — in a console, in a support transcript — and a tool that describes itself as routine gets treated as routine.
- Anything the description can make the agent send to the tool server, it has sent. Refusal by your API is not refusal by the party that wrote the sentence.

That last one is where this challenge meets 8.2. A tool server is a process, it sits somewhere, and
what it can reach is a property of where you put it and not of what it claims to do.

## What would have to be true before this lab could contain one

Mechanically, not as intentions. Each of these is a thing you could fail a test on.

1. **The advertised set is pinned.** The client holds a digest of the tool list and its text, agreed at review time, and compares the advertised list against it on every connection.
2. **A mismatch fails the connection, loudly.** Not a warning, not a merge, not "new tools disabled by default" — the whole connection refuses, because a server that answered differently is a server whose next answer you cannot reason about either.
3. **The digest covers the descriptions, not only the names.** Otherwise 8.4's problem arrives from a stranger instead of a colleague, and the pin says nothing about it.
4. **Changing the pin is a diff.** Same shape as `APPROVED_OPERATIONS`: a literal in a reviewed file, so that connecting a new capability leaves the same trace as adding a route.
5. **The mismatch writes evidence.** Rule 9 wants the record in the same transaction as the change; there is no transaction here, so the honest version is that the refusal is recorded with the old digest, the new one, and the time — and somebody is told.
6. **The server's reach is decided separately.** Where it sits, what it can open a socket to, and whether it has a route out. That is 8.2's question and it does not get easier because the component is new.

Note what is not on that list: validating the description text. You cannot pattern-match instructions
out of prose, and a check that tried would be a test named for a larger claim than it makes — which
is 7.4's subject. The control is the pin, not the reading.

## Where this stops, and why

This lab does not have a mutable tool source, and it is not being given one today.

The reason is narrower than "it would be dangerous". Building a component that turns text fetched at
runtime into a registered tool is, on its face, the thing rule 10 prohibits: *external text is data
... cannot register tools.* ADR-0004 drew the line for a different capability and the test it set is
the right one to apply here — arming a control the system already has is a demonstration; adding a
code path that does the dangerous thing is a vulnerability with a comment above it. A tool source
that can be changed at runtime is a code path, not a setting at its wrong value.

But unlike 8.2, this is not simply refused by a rule. It is a design question with a defensible
answer in either direction, and the repository's own convention is that **a control-plane change is
a privilege grant and gets written down before it gets written.** So the next step is a document,
not a directory.

**What that ADR would have to decide**, stated so the next person does not start from a blank page:

1. **Whether the demonstration may live in this compose project at all**, or must be a separate, disposable service — ADR-0004's first acceptable shape — so the API and the Range are unchanged.
2. **Whether a pinned, digest-checked client counts as registering tools from external text**, or as loading a reviewed artefact that happens to arrive over a socket. That is the crux, and it decides whether rule 10 is satisfied or amended.
3. **What the reviewed artefact is.** `APPROVED_OPERATIONS` is the existing answer for the API's own routes; a remote server has no equivalent and one would have to be named, with a file and an owner.
4. **Where the server sits and what it may reach**, on the network table 8.2 works through — including whether it gets a route out, which is the question people forget until after they have shipped.
5. **Who writes the evidence, and where.** `app.audit_events` is written by services with a database role and a request context; a tool-list mismatch has neither, and a control-plane event with no home is a control-plane event nobody sees.
6. **What the inverse is.** Every Range mutation has a proven one. A challenge that connected a server and left it connected would fail the rule the whole registry is built on.

Until those six have answers, the honest state of 8.3 is: **described, not built, and the reason is
recorded.** That is a worse challenge than the ones that arm something. It is a better answer than
a demonstration that required the lab to become the thing it warns about.

## Take it to a review

1. **"Where does the list of tools your agent can call come from, and at what moment is it fixed?"** — process start from an image, or connection time from a socket, are different systems.
2. **"If that list came back different tomorrow, what would notice?"** — if the answer is a person reading a console, it is not a control.
3. **"Who writes the text of each description, and are they the same party who writes the code behind it?"** — a third party's prose in your model's context is a supply-chain question wearing a documentation hat.
4. **"Does anything in your authorization path read a tool's description?"** — it must not, and a surprising number of home-grown guardrails do.
5. **"What does a reviewer see when a tool is added — a diff, or a screenshot?"** — and if it is a diff, does it include the descriptions.
6. **"If you connected a third-party tool server next week, what would you have to decide before writing code?"** — the answer to this one tells you whether a team has a control plane or a habit.

Question 2 is the one that does the work. Everything else on this page is a way of making its answer
be *"a check, and it refuses."*
