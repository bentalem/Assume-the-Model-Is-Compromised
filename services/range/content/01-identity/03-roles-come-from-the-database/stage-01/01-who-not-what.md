# A token says who, not what

Three stages get collapsed into one word, and the collapse is where systems fail.

| | The question | Where the answer comes from |
|---|---|---|
| **Authentication** | is this token real? | a cryptographic signature |
| **Identification** | who does it name? | the `sub` claim |
| **Authorization attributes** | what is this person? | **the server** |

The first two genuinely are the token's job. The third is not, and it is the one that ends up in
there anyway — because the roles are right there in the payload, and reading them is one line
shorter than loading them.

```python
# One line. Fast. Wrong.
roles = token["realm_access"]["roles"]

# Three lines, a round trip, correct.
subject = memberships.load_subject(token.subject, token.authentication_level)
```

## What a token actually is

**A snapshot, taken at login.**

Revoke a role at 10:00 and a token minted at 09:58 still carries it. It will keep carrying it until
it expires, which is however long the identity provider was configured to allow — five minutes, an
hour, eight hours, and in one memorable case a refresh token valid for thirty days.

For that whole window, a system that reads roles from the token is enforcing a decision that was
reversed.

> **Roles in a token are cached authorization with no invalidation.** Nobody would design that on
> purpose; it arrives by reading a field that was already there.

## The revocation question

This is the question to ask, and it is short:

> **A user's role is revoked. How long until the system stops honouring it?**

| The answer | What it tells you |
|---|---|
| "Immediately" | roles are loaded per request. Ask to see the line |
| "When their token expires" | roles are in the token. Now ask how long tokens last |
| "They'd have to log out and back in" | the same answer, said more comfortably |
| "We'd revoke the session too" | ask what happens to a token already issued and in flight |

None of those is automatically wrong. A five-minute window is a decision somebody can defend. A
thirty-day one usually means nobody knew there was a decision to make.

## Why this gets sharper with an agent in front of it

Two reasons, and the second is the one people miss.

**Sessions last longer.** A chat window stays open across a morning. A human clicking through a UI
re-authenticates naturally; an agent conversation does not, and neither does the token behind it.

**Nobody is watching the screen.** A revoked permission being exercised by a person tends to get
noticed by that person. An agent acting on a role its user no longer holds produces no surprise
anywhere — it just keeps working, correctly, on the wrong authority.

## What you are about to do

Read a restricted customer as bob, who is a manager and therefore sees the whole record.

Then revoke his manager membership — **without touching his token, reissuing it, or invalidating a
session** — and ask again with the same credential.

If roles came from the token, nothing would change. Watch what does.
