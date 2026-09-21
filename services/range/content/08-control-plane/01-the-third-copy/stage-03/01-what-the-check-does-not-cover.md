# The third copy is a paste

```
copy 1   the code                        source of truth
copy 2   openapi/supportpilot-actions.json   checked against copy 1 on every commit
copy 3   the agent's registered actions      a person, once, at setup
```

The check compares copies 1 and 2. Copy 3 is made by opening an admin panel and pasting the
document into a form, because the setup script says so in as many words: *"Left to you, because
both need an Onyx admin login this script does not have."*

So on Wednesday, the agent still believes it has the tool that was deleted on Tuesday. It will try
to call it. The API will refuse, because the route no longer exists — which is the good news, and
also the whole shape of the lesson.

## Both directions, and only one of them is safe

This is the part worth taking away, because the two directions of drift are not symmetric.

| Drift | What the agent does | What happens |
|---|---|---|
| Agent knows a tool the code **removed** | calls something that is gone | the API refuses. **Fails closed** |
| Agent knows a tool whose **schema narrowed** | sends the old shape | schema validation refuses. Fails closed |
| Agent does **not** know a tool the code added | never calls it | a capability silently missing |
| Agent holds a **description** that is no longer true | uses the tool wrongly, or avoids it | no error, no signal, nothing refuses |

The first two are fine. This system enforces authority at the boundary, not from the document, so a
stale tool list cannot grant anything — the agent asking for a route that does not exist gets the
same refusal as anyone else. That is invariant 2 doing its job, and it is the reason this finding is
a reliability finding rather than a security one.

The last two are the interesting ones, and the fourth is the one nobody looks for. A description is
not validated by anything: the API has no opinion about the prose, and there is no schema for "is
this sentence still true". An agent working from a stale description does not fail — it just works
from a wrong idea about what a tool is for, indefinitely.

## What the passing check entitles you to conclude

Entitled to conclude:

- the document describes the code as it is now
- an agent registered **from today's document** would have the right tool list

Not entitled to conclude:

- that any agent was registered from today's document
- that the agent's list matches anything at all
- that anyone would find out if it did not

> A green check tells you two artifacts agree. It says nothing about a third artifact it cannot
> read. **The gap is not in the check; it is in what people believe the check covers.**

## Why this generalises past agents

Everything above is true of any configuration that lives in a system your pipeline cannot reach: a
webhook, an IAM role made in a console, a feature flag, a DNS record, a scheduled job in a SaaS
product. Agent tool lists are just the newest and most powerful example, because this one decides
what an automated actor is allowed to attempt against production.

The question that finds all of them is the same:

> **"Which of your controls lives somewhere your deployment pipeline cannot see?"**

## What to recommend

Be proportionate. "Automate the registration" is the obvious answer and frequently not available —
the admin API may not exist, or may not be exposed.

1. **Make the copy readable.** If the platform can be queried for its registered actions, query it
   in CI and diff against the document. That converts an invisible gap into a failing build.
2. **Version the document and record which version was registered.** Even a note saying *"registered
   from build 41 on 3 March"* turns "we do not know" into a question with an answer.
3. **Put re-registration in the runbook for tool changes.** If step 4 is a human step, it belongs in
   writing next to steps 1 to 3, not in somebody's memory.
4. **Treat descriptions as part of the change.** Challenge 8.4 is about who may change that text;
   this challenge is about whether the change ever arrives.

## Take it to a review

1. **"How many copies of the tool list exist?"** Count them out loud. Three is common; people say
   one.
2. **"What gets the list from the repository into the agent, and when did it last run?"** If the
   answer is a person, ask when.
3. **"Can you read back what the agent is registered with?"** If not, nothing can diff it.
4. **"If a tool were removed today, what would the agent try tomorrow?"** Then check that the
   boundary — not the document — is what refuses it.
5. **"Who reviews the tool descriptions?"** The answer is usually nobody, and stale prose is the
   drift that never throws an error.

Question 4 is the one that separates a reliability finding from a security one, and you want to know
which you are writing before you write it.
