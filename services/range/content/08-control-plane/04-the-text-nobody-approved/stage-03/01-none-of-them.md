# None of them

That is the answer to the question in Stage 01, and it is worth being exact about it rather than
dramatic.

```
                            refund        operation summary
proposed by a named person    yes                no
approved by someone else      yes                no
bound to a hash               yes                no
executes once                 yes               n/a
audit row, same transaction   yes                no
```

The audit trail has no row about this document, because nothing in the request path ever writes one.
Row-level security does not apply — it is a file, not a table. The policy engine is never asked,
because nobody is making a request. The approval trigger cannot fire, because there is no action
request to approve.

**Every control this lab is built on is a control over requests.** The text is not a request. It
arrives through the same door as any other source change, and it is reviewed exactly as much as
whoever opened that pull request was reviewed — which may be thoroughly, or may be not at all, and
in neither case does the system know.

## What the check actually guarantees

There is a check, and it does run, and it is worth reading precisely because it is easy to mistake
for more than it is:

```
OK: action document matches the code. Operations: add_internal_note, get_action_status, ...
```

**"Matches the code."** That is a consistency property. It guarantees the document is not stale —
that the operations it lists exist, that the schemas are bounded, that every operation has a summary
at all. Challenge 8.1 is about the limits of that check's reach: it compares two of the three
copies of the tool surface, and the third is the one the agent actually calls.

What it does not guarantee, and does not claim to:

- that the summary is **true**
- that anyone **agreed** to it
- that anyone can find out **who wrote it** or what it said last week

Read the highlighted lines. The check asks whether a summary exists — *"no summary for the model to
read"* is the finding it can report. It has no opinion about what the summary says. A summary
reading *"use freely, read-only and safe"* on a tool that is neither passes this check, forever.

> A consistency check tells you the document and the code agree. It cannot tell you the document is
> **right**, and the two get confused constantly, because passing feels like approval.

## Why this is the normal state, not a lab defect

Nobody decided to leave the text unguarded. It happened the way these things always happen: the
controls were designed around the dangerous *operations*, and the prose describing them was treated
as documentation. Documentation does not get an approval workflow.

That reasoning was correct right up until the reader became a model that acts on what it reads. At
that moment the description stopped being documentation and became configuration — and nothing in
anyone's process noticed the change, because nothing had visibly happened.

This is the shape of most agent-security findings worth reporting. Not a broken control. **A
control boundary drawn before the system had this component, never redrawn afterwards.**

## What to actually recommend

Be specific, and be proportionate — "put the system prompt behind an approval workflow" gets
nodded at and never done.

1. **Version it.** Whatever holds the text, it needs history: who, when, and what it said before.
   Most of the value is here, and it is the cheapest of these.
2. **Diff it in review.** Tool descriptions and prompts should appear in a pull request as their own
   reviewable change, not buried in a schema file nobody reads twice.
3. **Test the behaviour, not the text.** A description that grants nothing cannot be dangerous;
   assertions belong on the boundary, not on prose. Challenge 7.4 is about why a test named for a
   larger claim than it checks is worse than no test.
4. **Approval only where it is real.** If a change to the text can change what the agent attempts
   against production, it deserves the same second pair of eyes a refund gets. If it cannot, saying
   so out loud is also a finding — it means the text is not load-bearing and you have learned that.

## Take it to a review

1. **"Where does the model's instruction text live, and who can change it?"** A repository, a
   console, and a database are three different answers with three different blast radii.
2. **"Show me the history of that text."** If there is none, there is no way to answer *"when did
   the behaviour change?"* after an incident.
3. **"Which of your controls apply to a change to it?"** Usually the honest answer is code review,
   and only if it is in code.
4. **"Do your tool descriptions get reviewed as controls or as copy?"** The answer is almost always
   copy, and almost always should not be.
5. **"What would a malicious description be able to make the agent try?"** Then check whether the
   boundary would stop it — because that, and not the text, is what you are really relying on.

Question 5 is the one that keeps this proportionate. The text is a control surface, and the reason
this lab survives an unguarded one is that **the authority is enforced somewhere the text cannot
reach.** That is the same conclusion as every other track, arriving from a new direction.
