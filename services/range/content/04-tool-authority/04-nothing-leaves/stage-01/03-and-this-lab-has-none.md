# And this lab has none

## And this lab has none of it

There is no outbound tool here, and that is a decision rather than a gap somebody forgot to fill.
This lab forbids the general case outright — no SQL, shell, file or unrestricted HTTP tool — and
puts every sensitive effect through propose, approve, execute, with the API never performing it in
the request path. A tool that sends is an irreversible effect with no rollback, so it falls under
the second of those, not the first.

Adding one to teach this challenge would have meant shipping the capability in every image of the
service the lab holds up as the well-built one. So the challenge teaches the audit instead, and the
absence is the thing you are asked to prove.

## Your task

1. Establish, from the surface rather than from this page, that no registered operation sends
   anything outside the system. Say what you read and what would have shown up if one did.
2. Be precise about what the absence is. *"This system cannot make an outbound connection"* is a
   claim you have not checked and it is not the one worth making. Write the narrower one.
3. One component here genuinely is built to reach outside. Find it. Say where it lives, what gates
   sit between the model and it, and which of those gates is a property of the code rather than a
   configuration setting.
4. Then write the useful half: the day somebody proposes `send_customer_email`, which of this lab's
   existing controls already covers the recipient, and what would have to be built for the content?

Question 4 is the one that survives contact with a real system, because most teams asking you to
review an agent already have the outbound tool.
