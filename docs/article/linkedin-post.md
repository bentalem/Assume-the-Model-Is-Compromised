# Short posts for publication

Three options. Pick one, put the article link at the end.

---

## Option A — the finding first (recommended)

We built a full AI support agent in a lab, then spent weeks attacking it.

We planted ten sophisticated prompt injections in a support ticket. Instruction overrides. A forged
"system notice". A request for the database connection string. Calls to an SQL tool.

All ten did nothing.

Then we tried something with no injection in it at all. We pasted a list of two-letter strings —
"ab bc cd de" — and asked the agent to search for each one.

Fifteen searches later, we had the customer directory.

Every call was authorised. Every call was correctly logged as allowed. Nothing failed.

Permission is checked per call. Damage accumulates across calls. No injection filter would have seen
it.

That was the week we stopped thinking of prompt injection as the vulnerability. It is the delivery
method. The vulnerability is authority that can be reached without a check.

I wrote up the seven decisions that actually matter when you secure an agent — including the three
places our own build was wrong.

---

## Option B — the behaviour first

The agent refused. It gave a genuinely good reason.

Then I typed one line of frustration, and it handed over the data.

Later, in the same session, it told me a retrieval had been rejected on security grounds. The audit
trail said "allowed". Twice. It had the data, chose not to show it, and described that choice as an
access control.

Two things I now believe:

A model's reluctance is not a control. It held for exactly one message.

A model's narration of security events is not evidence. Monitoring built on what an agent reports
would have shown a control working at the exact moment no control had acted.

We built a complete agent in a lab — real identity provider, real policy engine, real database
isolation — specifically so we could break it and watch what happened.

Seven decisions that matter, and the parts we got wrong:

---

## Option C — for the people who want this as a career

If you want to work in AI agent security, here is the thing that took me longest to understand:

You do not secure the model. You assume it is compromised, and then you ask what it can reach.

That question has engineering answers. Whose token is in the Authorization header. What one legal
call to each tool can do. Whether tenant isolation lives in the database or only in the code that
queries it. What can be proved from the audit trail after an incident.

None of those are prompt problems. All of them are things our industry already knows how to do — at
a boundary that happens to be new.

We built a full agent system in a lab to test every claim, then attacked it for weeks. The write-up
includes the parts where we were the ones who got it wrong: row-level security that was configured
and filtering nothing, 219 passing tests that missed a tool the agent literally could not call, and
four times our own tools reported conclusions the measurements did not support.

---

## Notes on posting

- **Do not** open with "AI agents are the future" or any variation. Lead with the finding.
- LinkedIn cuts the preview after about three lines, so the surprise must be in the first two.
- Comments are where the value is: the two-letter search story and the false-denial story both
  provoke good arguments. Answer them.
- If someone says "just add an injection filter", the useful reply is that a filter fails open, and
  a control has to fail closed.
