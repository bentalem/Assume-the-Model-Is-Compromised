# The revocation question

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

Then demote him to a support agent — **without touching his token, reissuing it, or invalidating a
session** — and ask again with the same credential.

If roles came from the token, nothing would change. Watch what does.
