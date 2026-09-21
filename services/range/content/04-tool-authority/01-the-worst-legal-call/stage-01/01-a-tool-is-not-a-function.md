# A tool is not a function

This is the track that distinguishes the role, and the reason is that almost nothing here has an
equivalent in classical security. Identity, authorization, tenant isolation, audit — good engineers
already know those. This one they have not been asked about.

> **A tool is not a function. It is a grant of standing authority to something that is untrusted
> input and steerable by the text it reads.**

The same function already exists in the UI, and it is fine there. What changed is the caller:

| | The UI | The agent |
|---|---|---|
| Who decides to call | a person, on purpose | a model, influenced by what it read |
| How many times | once, per click | a hundred, per second |
| Who picks the arguments | a form with one field | the model, freely |
| Can it be steered by data | no | **yes — that is the whole threat** |

So when a team says *"it's the same API our web app uses"* — true, and beside the point. **The threat
model changed; the API did not.**
