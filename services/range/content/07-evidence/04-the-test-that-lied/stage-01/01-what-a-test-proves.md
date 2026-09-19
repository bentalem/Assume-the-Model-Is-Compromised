# What a passing test actually proves

A green suite feels like evidence. Usually it is — but of a narrower claim than the one in the test
name, and the gap between those two is where confident wrong answers come from.

Every test makes three separate claims, and only one of them is checked by running it:

| Claim | Checked by running it? |
|---|---|
| *This specific request produced this specific result* | **yes** |
| *Therefore the control it covers is working* | only if the assertion actually exercises the control |
| *Therefore the property in the test's name holds* | **never** — that is a human claim, written in prose |

The third one is what people read. It is the line in the CI output, the row in the coverage report,
the sentence quoted in the security questionnaire. And nothing verifies it.

## Why the name matters more than it looks

The name is the interface. It is what a reviewer reads six months later, what an auditor is shown,
and what stops the next person from writing the test that *would* have caught the thing.

> **A test named for a claim larger than its assertion does not merely fail to catch a problem. It
> actively stops anyone from looking.**

A missing test is a gap someone might notice. A test named *"bulk extraction is impossible"* is a
gap with a sign on it saying the ground has been checked.

## The shapes this takes

**The name is a property; the assertion is an instance.** *"Users cannot access other tenants"* that
checks one user and one record. True for that pair. Silent about the fiftieth endpoint.

**The name is a negative; the assertion is a positive.** *"X is impossible"* proving that one attempt
at X was refused. Impossibility is not something a single request can establish — and the test
usually cannot establish it at all, which is why the name should not claim it.

**The assertion tests the wrong layer.** A request is rejected and the test concludes the control
worked, when it was refused by schema validation and never reached the control at all. This is
challenge 7.3, and it is the same disease.

**The assertion tests a mechanism that enables the thing the name denies.** The rarest and the worst,
because the test is not weak — it is thorough, careful, and pointed in the opposite direction from
its name. That one is in the source below.

## The discipline

Two rules, and they are cheap:

1. **Name a test for what it proves.** If the name is a larger claim than the assertion, change one
   of them — and changing the name is a valid fix.
2. **Ask what it would take for this test to fail.** Then check whether the property in the name is
   on that list. If it is not, the name is wrong.

The second one takes about thirty seconds per test and is the single highest-value thing you can do
to somebody else's test suite.
