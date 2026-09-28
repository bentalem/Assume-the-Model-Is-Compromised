# The case, and what it really proves

`TS7-09` — **"Bulk extraction is impossible: pagination is capped server-side."**

## What your result proves

Three assertions, and all three are good:

1. A search asking for `limit=50` comes back with **at most 25 rows**, because the policy obligation caps it server-side. Real control, correctly verified.
2. The match set is larger than one page, so a `next_cursor` **is** returned. Deliberate: the comment above it explains that the search term was chosen to exceed the cap, because otherwise any page size would look correct. That is a careful test.
3. The second page **does not repeat the first**. As its comment says, a broken cursor that restarts would be an unbounded walk dressed up as pagination.

This is not a lazy test. It is more thoughtful than most tests you will read. And its name claims that bulk extraction is **impossible**.

Look at what assertions 2 and 3 verify. They verify that **paging works**: that a cursor is issued, and that following it advances through the match set without repeating.

A correctly working cursor is not a defence against bulk extraction. **It is the mechanism for it.** Follow it to exhaustion and you have every row, a page at a time, with every request inside every limit and every one of them logged as `allowed`.

That sentence is the button in the console. It prints how many calls it made, how many distinct customer records those calls reached, and whether every one of them was allowed. Nothing refused it, nothing counted it, and `TS7-09` was green the whole time it ran.

> The test proves the page cap holds. The name claims the *total* is bounded. Nothing in the file bounds a total, because nothing in the system does.

And the third assertion — the most rigorous one in the case — is a proof that the extraction path is reliable.

## Where the control lives

The control this test covers is real, and it lives in the policy: the `max_results` obligation on `customer.search`, applied by the API before the query runs. That is a **per-request** control, and the test verifies it correctly.

The control its name describes would be a **per-session** one, and it lives nowhere:

- `AGENT_MAX_TOOL_CALLS` is `8` in `.env.example`, and no service in this repository reads it. The same number is a setting you enter in Onyx by hand when you build the agent (LAB.md, B11): Onyx stops a single turn after eight tool calls — if somebody set it. The next turn starts again from zero, and nothing totals a session.
- `rate_limited()` is defined in the API's `errors.py` and raised nowhere.

So the ceiling on how much of the directory one conversation can reach is, at most, a per-turn setting in the agent runtime — no injection, no bug, and every call correctly logged as `allowed`.

## What this check does not cover

There is nothing to restore; nothing was armed. The suite was green against exactly this system, and that is the finding.

The honest version of the case says what it proves:

```
TS7-09  "A single search page is capped at the policy's max_results, and the
         cursor advances without repeating"
```

Longer, duller, and true. Then the gap becomes visible instead of being covered by the old name, and somebody writes the test that is actually missing:

```
TS7-15  "A session cannot retrieve more than N customer records in total"
```

That test does not exist, and it cannot be written yet, because **the control it would cover does not exist either.** Which is the real finding — the missing control was hidden behind a test name that said it was handled.

## Take it to a review

1. **Read the names with the bodies covered.** Sort them into claims about a request and claims about the world. The second pile is your list.
2. **For each one, list what would make it fail.** If the property in the name is not on that list, the name is wrong — and renaming is a valid fix.
3. **"Show me a test that failed when you removed the control it covers."** A negative test nobody has watched go red has never been switched on.
4. **"Where is the per-session limit, and which test covers it?"** If the answer is a per-request test, the limit does not exist yet.

When a test name makes a claim about a **total**, a **limit over time**, or something being **impossible**, check whether any assertion in it measures across more than one request. Usually none does — because a test is a request, and a total is not.

> **Per-request tests cannot establish per-session properties.** If the name claims one, the control is either somewhere else or nowhere.
