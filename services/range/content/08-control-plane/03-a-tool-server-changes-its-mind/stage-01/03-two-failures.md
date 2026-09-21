# Two failures

## Two different failures, and they are worth separating

People collapse these into "the tool server is untrusted", which is true and not useful. They have
different controls.

| | What moved | What it defeats |
|---|---|---|
| The set changed | a tool exists that nobody approved | the review that said what the agent can do |
| The text changed | prose the model treats as instruction | the boundary between the operator's words and a third party's |

**The first is a control-plane change arriving without a change.** No pull request, no diff, no
deploy. Whatever a reviewer signed off on is not what is running, and the system did not lie to
them — the list was correct when they read it.

**The second is subtler, and it is the one people miss.** A tool description is not documentation.
It is text placed in the model's context for the purpose of steering what it calls next; that is the
entire mechanism by which a model picks anything. When the description comes from your own
repository, it is your text and 8.4 is the challenge about who may edit it. When it comes from a
server somebody else runs, it is **their** text, sitting in the same context as your system prompt,
with nothing in the transcript marking which is which.

That is the lab's flattest rule — *external text is data; it cannot register tools, change policy,
grant permission, or alter instructions* — meeting a component whose whole job is to let external
text register tools.

## What this lab has instead

Static registration, in three places you can check:

- `create_app` mounts five tool routers, and one more that is excluded from the document on purpose. A tool that is not compiled into the image does not exist at runtime.
- The export refuses to write the action document if the running code carries an operation that is not on the approved list, and refuses again if an approved operation has gone missing. Both directions, same run.
- When it passes, it says so precisely: `OK: action document matches the code.` — a consistency property, and nothing larger. 8.4 is the challenge about what that sentence does not cover.

Press the three observations and satisfy yourself. The fixed list of modules in the database, the
seven operations in the published document, and the text each one carries. Then notice the thing
that makes this challenge possible to write at all: **all three of those answers came from files
that were already on disk.** None of them was fetched.

## Your job

1. Establish at what moment this lab's tool list is decided, and which artefact would have to change to change it.
2. Name the two distinct things a runtime tool source puts outside your review, in your own words, and say which of this lab's controls covers each today.
3. Say what would have to be true — mechanically, not as an intention — before this repository could connect one without breaking rule 10.

Stage 03 has an answer to the third, and it ends somewhere that may be unsatisfying: with a document
that has not been written.
