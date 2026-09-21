"""The Range's prose: the landing page's copy, and the long-form guide behind it.

Kept as Markdown in its own module rather than as HTML in `render.py`, because it is prose that will
be edited by whoever is teaching rather than by whoever is maintaining the renderer, and because the
Markdown subset already escapes before it adds markup.

The track list is NOT written here. It is generated from `TRACKS` and `TRACK_CLAIMS` at render time,
so a track renamed in one place cannot go stale in the other — which is the failure this repository
has spent most of its history correcting.
"""

from __future__ import annotations

OPENING = """
This is a practice range for **securing AI agents**. It runs against a real system — a support
agent with real tools, a real policy engine, a real database with row-level security, and a real
approval workflow for anything that moves money.

Nothing here is a simulation of a vulnerability. Each challenge either breaks a control that
genuinely exists and lets you watch the consequence, or shows you a property the system genuinely
has and asks you what it is worth.

> **You never need a terminal.** Everything happens in this browser. You will not be asked to
> install anything, edit a file, or run a command.
"""

STAGES = """
## A challenge has three stages, in order

Every one of the thirty-one challenges is laid out the same way, and the order is deliberate:
you cannot learn anything from breaking something you did not understand first.

| Stage | What it is | What you do |
|---|---|---|
| **01 · Learn** | the idea, in one or more tabs | read it — there is a *skip test* at the top telling you when you may skip |
| **02 · Break it** | the console | arm a control, run observations, submit the flag |
| **03 · Understand** | the answer, and what to do with it | read it *after* Stage 02, not before |

Stage 01 opens with a **skip test**: one sentence saying what you would already have to know in
order to skip the reading. If you can answer it, go straight to the console. If you cannot, the
reading is short and it is the reason the rest will make sense.

Stage 03 always ends with **"Take it to a review"** — the questions a reviewer would actually ask
about a real system. That list is the transferable part. The flag is just how you prove you got
there.
"""

CONSOLE = """
## The console, and what it actually sends

Stage 02 has two panels. On the left, the environment: the controls this challenge can break, and
the observations it can run. On the right, the result of whatever you last pressed.

- **Arm** puts one named control into its wrong setting. The console says loudly that it is armed.
- **Restore** puts that one control back.
- **Observe** runs a named, fixed query or request and shows you what came back.
- **Reset the environment** asserts *every* control in the lab, not just this challenge's, and
  tells you which ones it had to put back.

Three things are worth knowing about how this works, because they are also a lesson:

1. **Your browser only ever sends an id.** There is no endpoint here that accepts SQL, a role, a
   file path, a container name or a URL. Adding a control means editing a file that somebody
   reviews. That is the same design the agent itself is built on.
2. **Every control has a proven inverse**, and a probe that reports its real state by asking the
   system rather than remembering what it was told. If a probe cannot tell, it says `unknown` — it
   never says `correct` on a guess.
3. **Arming is recorded.** The Range writes to the same audit trail the rest of the lab uses, so
   the things you break appear in track 7's evidence alongside everything else.

> **Reset before you leave a challenge.** If you walk away with something armed, every measurement
> you take in the next challenge is a measurement of that instead. Challenges that arm something
> say so at the end of Stage 03.
"""

FLAGS = """
## Three kinds of flag

Not every challenge is answered the same way, because not every lesson is a string.

| Kind | What you submit | How it is checked |
|---|---|---|
| `value` | a number or a name | against what an observation returns **right now** |
| `reason` | a reason code from the audit trail | against the code the control actually recorded |
| `written` | two or three sentences | against the points a correct answer has to contain |

The `value` flags are the strict ones: where a challenge arms a control, the answer is a value that
**does not exist** while the control is intact. You cannot guess it and you cannot look it up — the
only way to obtain it is to break the thing and read the result. The suite checks that property on
every run.

The `written` flags are scored on whether your answer contains the points that matter, not on
wording. They are deliberately the hardest to fake, and they are the ones closest to what you would
actually write in a report.
"""

TRACKS_INTRO = """
## The eight tracks

Each track makes one claim. The challenges inside it are the evidence for that claim.
"""

READING = """
## Reading a challenge honestly

Two habits this range is built to teach, and both of them are on every page:

**Ask whether something was prevented or whether it merely failed.** A request that was refused by
a control and a request that never reached the pipeline look identical from outside. They are
completely different findings, and only one of them is evidence that anything is working.

**Check what a claim actually covers.** A passing check tells you a specific thing. It usually does
not tell you the thing people believe it tells them, and the gap between those two is where most
real findings live.

You will also find, in several places, a challenge saying plainly that **the lab does not have the
capability its design asked for**, and why adding it would be the wrong thing to do. Those are not
gaps in the material. Refusing to build a fail-open path in order to demonstrate fail-open is the
same judgement the course is trying to teach.
"""

START = """
## Where to start

If you are new to this, go in order: **1.1**, then **2.1**, then **3.1**. Those three between them
establish identity, the database layer, and the policy layer, and almost everything later leans on
them.

If you are short of time and want the part with the least classical-security equivalent, read
**track 4**. Tool authority is the thing that genuinely does not exist in a system without an agent,
and 4.1 is the question you will end up asking in every review you ever do.

If you already work in security and want to know whether this is worth your time, open **7.3** and
**7.4**. They are about reading evidence and reading tests, and if they tell you nothing new then
the rest probably will not either.

Each challenge names what you are practising and how it relates to agents, at the top of its own
page — including the ones where the honest answer is *"this is ordinary application security, and
here is what an agent changes about it."*
"""

CLOSING = """
## What this is not

There are **no accounts, no scoreboard and no timer**. Nothing here knows who you are. Progress is
whatever you remember, plus whatever your browser remembers.

It is also not a set of puzzles with hidden tricks. Every answer is reachable by reading what is in
front of you and running the things on the page. If you are stuck, each challenge has up to three
hints, and every one of them is a question rather than an answer.
"""


# --------------------------------------------------------------------------------------------------
# The landing page.
#
# Short on purpose. It has one screen to say what this is, show the eight tracks, and put somebody
# in a challenge, so every sentence here has to earn its line. The numbers are NOT written here —
# the renderer counts what actually loaded — and neither is the track list.
# --------------------------------------------------------------------------------------------------

LANDING_TITLE = "Break a real agent, on purpose, and then put it back."

LANDING_STANDFIRST = (
    "A practice range for securing AI agents, built on a real one: real tools, a real policy "
    "engine, a real database with row-level security, and a real approval workflow for anything "
    "that moves money."
)

LANDING_SUB_1 = (
    "Nothing here is a simulation of a vulnerability. Each challenge either breaks a control that "
    "genuinely exists and lets you watch the consequence, or shows you a property the system "
    "genuinely has and asks you what it is worth."
)

LANDING_SUB_2 = (
    "You never open a terminal. If a challenge needs a command, the Range runs it, says what it "
    "ran, and can put every control back in one press."
)

ROUTE_NEW = (
    "Go in order. Identity, then the database layer, then the policy layer — almost everything "
    "later leans on those three, and they take about an hour between them."
)

ROUTE_SHORT = (
    "Tool authority is the part with no classical-security equivalent. 4.1 is the question you "
    "will end up asking in every review you ever do."
)

ROUTE_PRO = (
    "Start where the material is hardest to fake: reading evidence, and reading a test. If these "
    "two tell you nothing new, the rest probably will not either."
)

# One line per stage, in order, for the strip at the foot of the landing page.
STAGE_LINES = (
    "The idea, in one or more tabs, with a skip test at the top telling you when you may skip it.",
    "The console. Arm a named control, run a fixed observation, read what came back, submit the flag.",
    "The answer, the lab's own source with line numbers, and the questions a reviewer would ask.",
)

GUIDE_TITLE = "How to use The Range"

GUIDE_STANDFIRST = (
    "How a challenge is laid out, what the console is allowed to do, how the three kinds of flag "
    "are checked, and where to start. Four minutes, and it is the only page here that is not a "
    "challenge."
)
