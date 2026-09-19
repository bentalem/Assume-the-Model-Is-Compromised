# The case, and what it really proves

`TS7-09` — **"Bulk extraction is impossible: pagination is capped server-side."**

## What it checks

Three assertions, and all three are good:

1. A search asking for `limit=50` comes back with **at most 25 rows**, because the policy obligation
   caps it server-side. Real control, correctly verified.
2. The match set is larger than one page, so a `next_cursor` **is** returned. Deliberate: the comment
   above it explains that the search term was chosen to exceed the cap, because otherwise any page
   size would look correct. That is a careful test.
3. The second page **does not repeat the first**. As its comment says: *"a broken cursor that
   restarts would be an unbounded walk dressed up as pagination."*

This is not a lazy test. It is more thoughtful than most tests you will read.

## What its name claims

That bulk extraction is **impossible**.

## Why those are opposites

Look at what assertions 2 and 3 verify. They verify that **paging works**: that a cursor is issued,
and that following it advances through the match set without repeating.

A correctly working cursor is not a defence against bulk extraction. **It is the mechanism for it.**
Follow it to exhaustion and you have every row, twenty-five at a time, with every request inside
every limit and every one of them logged as `allowed`.

> The test proves the page cap holds. The name claims the *total* is bounded. Nothing in the file
> bounds a total, because nothing in the system does.

And the third assertion — the most rigorous one in the case — is a proof that the extraction path
is reliable.

## What an honest version says

```
TS7-09  "A single search page is capped at the policy's max_results, and the
         cursor advances without repeating"
```

Longer, duller, and true. Then the gap becomes visible instead of being covered by the old name, and
somebody writes the test that is actually missing:

```
TS7-11  "A session cannot retrieve more than N customer records in total"
```

That test does not exist, and it cannot be written yet, because **the control it would cover does
not exist either.** Which is the real finding — the missing control was hidden behind a test name
that said it was handled.

## This is not hypothetical

This lab's own agent was later asked to search for fifteen two-letter strings in one message. It made
fifteen authorised calls and returned the customer directory. No injection, no bug, every call
correctly logged as `allowed`.

`TS7-09` was passing the whole time.

## The habit

When a test name makes a claim about a **total**, a **limit over time**, or something being
**impossible**, check whether any assertion in it measures across more than one request. Usually
none does — because a test is a request, and a total is not.

> **Per-request tests cannot establish per-session properties.** If the name claims one, the control
> is either somewhere else or nowhere.
