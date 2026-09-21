# Why a name check misses it

## Why a name-based check cannot find it

This repository audits its own action document before publishing it, and the audit has a list of
parameter names it refuses — `user_id`, `organization_id`, `role`, `approved` and the rest. That
list exists for rule 1, and it works, because the identity fields a model must never supply have
well-known names.

Genericity has no well-known name. There is no word you can ban. `parameters`, `options`, `context`,
`metadata`, `extra`, `payload`, `config`, `args` — all ordinary, all innocent nine times out of ten.
The only thing that distinguishes the tenth is the shape, which means the check has to be about the
shape, which means somebody has to have written that check.

## Your task

Read the whole surface, not the interesting part of it. Seven operations; count every parameter and
every request body field, and for each one write down whether it declares what it accepts.

Then answer three things:

1. Is any parameter or body property typed `object` with no declared properties? Say how you
   established it, rather than that you looked.
2. The two POST operations do carry a body typed `object`. What makes those bodies bounded, in the
   document rather than in the code?
3. Go to `scripts/export_openapi.py`. It is the gate the document passes through. Which of its rules
   would have rejected the `run_saved_report` above, and which would have let it through?

Question 3 is the one worth your time. A surface that is clean today is a fact about today. A check
that would catch it is a fact about next quarter.
