# The third copy is a paste

## What your result proves

```
copy 1   the code                               source of truth
copy 2   openapi/supportpilot-actions.json      checked against copy 1 whenever the check runs
copy 3   the agent's registered actions         a person, once, at setup
```

The check compares copies 1 and 2. Copy 3 is made by opening an admin panel and pasting the document into a form, because the setup script says so in as many words: *"Left to you, because both need an Onyx admin login this script does not have."*

So on Wednesday, the agent still believes it has the tool that was deleted on Tuesday. It will try to call it. The API will refuse, because the route no longer exists — which is the good news, and also the whole shape of the lesson.

### What the passing check entitles you to conclude

Entitled to conclude:

- the document describes the code as it is now
- an agent registered **from today's document** would have the right tool list

Not entitled to conclude:

- that any agent was registered from today's document
- that the agent's list matches anything at all
- that anyone would find out if it did not
- that the check ran on every commit — it runs when somebody runs it, and the hook that would run it is not in the published repository

> A green check tells you two artifacts agree. It says nothing about a third artifact it cannot read. **The gap is not in the check; it is in what people believe the check covers.**

## Where the control lives

Not in the document, and that is what makes this a reliability finding rather than a security one.

The two directions of drift are not symmetric:

| Drift | What the agent does | What happens |
|---|---|---|
| Agent knows a tool the code **removed** | calls something that is gone | the API refuses. **Fails closed** |
| Agent knows a tool whose **schema narrowed** | sends the old shape | schema validation refuses. Fails closed |
| Agent does **not** know a tool the code added | never calls it | a capability silently missing |
| Agent holds a **description** that is no longer true | uses the tool wrongly, or avoids it | no error, no signal, nothing refuses |

The first two are fine. This system enforces authority at the boundary, not from the document, so a stale tool list cannot grant anything — the agent asking for a route that does not exist gets the same refusal as anyone else. That is rule 2 doing its job.

The last two are the interesting ones, and the fourth is the one nobody looks for. A description is not validated by anything: the API has no opinion about the prose, and there is no schema for "is this sentence still true". An agent working from a stale description does not fail — it just works from a wrong idea about what a tool is for, indefinitely.

## What this check does not cover

Nothing was armed, so there is nothing to restore. What the check cannot reach is copy 3, and the reason is structural rather than lazy.

Everything above is true of any configuration that lives in a system your pipeline cannot reach: a webhook, an IAM role made in a console, a feature flag, a DNS record, a scheduled job in a SaaS product. Agent tool lists are just the newest and most powerful example, because this one decides what an automated actor is allowed to attempt against production.

> **"Which of your controls lives somewhere your deployment pipeline cannot see?"**

What to recommend — proportionately, because "automate the registration" is the obvious answer and frequently not available:

1. **Make the copy readable.** If the platform can be queried for its registered actions, query it in a pipeline and diff against the document. That converts an invisible gap into a failing build.
2. **Run the check where it cannot be skipped.** A check that runs from a local hook proves something about the machines that installed it.
3. **Version the document and record which version was registered.** Even a note saying *"registered from build 41 on 3 March"* turns "we do not know" into a question with an answer.
4. **Put re-registration in the runbook for tool changes.** If step 4 is a human step, it belongs in writing next to steps 1 to 3, not in somebody's memory.
5. **Treat descriptions as part of the change.** Challenge 8.4 is about who may change that text; this challenge is about whether the change ever arrives.

## Take it to a review

1. **"How many copies of the tool list exist?"** Count them out loud. Three is common; people say one.
2. **"What gets the list from the repository into the agent, and when did it last run?"** If the answer is a person, ask when.
3. **"Can you read back what the agent is registered with?"** If not, nothing can diff it.
4. **"If a tool were removed today, what would the agent try tomorrow?"** Then check that the boundary — not the document — is what refuses it.
5. **"Who reviews the tool descriptions?"** The answer is usually nobody, and stale prose is the drift that never throws an error.
6. **"Where does this check run, and what happens if nobody runs it?"** A green line from a hook proves something about one machine.

Question 4 is the one that separates a reliability finding from a security one, and you want to know which you are writing before you write it.
