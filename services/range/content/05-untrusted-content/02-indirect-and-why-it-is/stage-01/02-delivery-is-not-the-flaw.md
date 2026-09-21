# Delivery is not the flaw

## Why the delivery is not the vulnerability

Here is the part that takes longest to accept.

There is no way to stop indirect injection. Instructions and data share one channel in a language
model — the same tokens, the same context, no separator. SQL injection was solved by giving the
database two channels and letting it tell them apart; there is no prepared statement for English.

So the useful question is not *"how do we stop the text getting in"*. It is:

> **Assume the text got in and the model did exactly what it said. What could it reach?**

Which is a question about tools, credentials and boundaries — all things you can change — rather
than about text, which you cannot.

## What you are about to read

Eleven messages on TKT-1001. One is a genuine complaint. **Nine are instruction-shaped**, written
to look like ordinary customer writing — eight of them by the customer, one by an agent. The
eleventh is an internal note marked `restricted`.

They are read by any agent working that ticket, through a completely ordinary permitted request.

**No content filter touches them.** There is no injection detector, no classifier, no scrubber; the
nine arrive intact and are summarised like anything else. One thing *is* filtered, and it is not a
filter for instructions: the `restricted` note is dropped by a row policy for anyone who is not a
manager or an auditor — so alice sees ten of the eleven, and the reason is her role, not the
content.

And none of them achieve anything.

Your job is to work out why — attempt by attempt — because "the model was sensible" is not the
answer, and if it were, it would not be a control.
