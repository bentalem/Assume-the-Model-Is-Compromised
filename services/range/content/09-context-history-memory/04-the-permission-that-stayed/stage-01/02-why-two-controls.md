# Why this challenge has two controls

This flag cannot be earned with one switch, and the reason is the lesson.

| bob | Revalidation | The email in his context is | |
|---|---|---|---|
| manager | on | **legitimate** | he may see it |
| manager | off | **legitimate** | he still may |
| demoted | on | **left out**, and the block says why | the control working |
| demoted | off | **included** | a permission that outlived itself |

With bob still a manager, the email in his context is correct, whatever revalidation says. The
failure exists only when the source of truth has changed **and** the copy is not checked against it.
The flag column is filled only in that last row: an item the log marks as having outlived its
permission.

## No incident to point at, and why

There is no famous breach named for this. It is the general "memory as a cache that bypasses
authorisation" pattern, and it tends to be found in review rather than in the news — because nothing
about it looks wrong from outside. The requests are ordinary, the user is real, and the data was
legitimately fetched once. Ask it of every memory system you review: **when a permission is
withdrawn, what stops the agent from still acting on what it saw?**

## What you are about to run

Run the observation first with nothing armed: bob, a manager, looks CUS-4003 up through the API, and
the runtime records what he was shown. Then arm one control at a time, and both.
