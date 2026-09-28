# Minting is not enforcing

A delegated token is a claim. It says: *this agent, acting for this user, may do this much.* A claim does nothing until something reads it and refuses what it does not cover.

So there are two jobs, and they belong to two different components:

| Job | Who does it | What it proves |
|---|---|---|
| **Minting** a narrow token | the issuer — here, the broker | the agent was *given* only what the task needs |
| **Enforcing** the scope on every use | the resource server — here, the API, through its policy | the agent can *use* only what it was given |

A design review that sees the first and assumes the second is the most common way this architecture fails. The token in the diagram is perfectly narrow. The API behind it checks the signature, loads the user, applies the user's roles — and never looks at `scope`.

## Why the gateway is not enough

The broker's gateway narrows every call that goes *through it*. But the agent holds its token, and nothing obliges it to use the gateway. A compromised agent calls whatever it likes, directly, with the token it legitimately obtained.

> The only component that sees **every** use of a token is the one that holds the data. That is where the scope has to be enforced.

This is the article's rule — enforcement lives with the data — arriving from the identity side.

## The mirror of 1.4

Challenge 1.4 rewrote a tenant claim in a token and found it changed nothing, because the API never read that claim. That was the good outcome: a claim the API does not act on cannot be used against it.

This is the same fact, and it is the bad outcome:

| | The claim | The API reads it? | Result |
|---|---|---|---|
| 1.4 | `organization_id: northwind` | no | a forged claim **changes** nothing |
| 1.6 | `scope: orders:read` | no | a genuine limit **narrows** nothing |

A claim the resource server ignores is inert in both directions.

## This was the API's state before this track

Before challenges 1.5 to 1.8 existed, the API's token verifier already parsed the `scope` claim into a field called `scopes`, and nothing in the API read it. Its docstring said the token *"carries identity only — no authority"*, and that was correct by design: every token came from Keycloak, and every decision came from the database.

The moment a second issuer starts minting narrowed tokens, that design has a gap. A narrowed token would have been accepted as the full user. So the scope check was added to the policy, where every other authorization rule lives. This challenge removes it again, to show you what the gap looked like.

**Next:** what you are about to run.
