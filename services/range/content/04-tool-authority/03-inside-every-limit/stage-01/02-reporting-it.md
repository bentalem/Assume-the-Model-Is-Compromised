# Reporting it

## Why this is the hardest kind of finding to report

There is no moment where the system did the wrong thing. If you go looking for a denial, a
suspicious pattern, a malformed request or an error, you will find none, because none happened.

Which means every instinct a reviewer has trained on classical security fires zero times here:

- nothing to detect — every call is a normal call
- nothing to block — blocking it would break pagination
- nothing in the logs that stands out — unless you are counting, and nothing counts

> **Permission is evaluated per call. Damage accumulates across calls.** A system that evaluates
> each request correctly, every time, can still hand over everything.

## What to do

Run the enumeration. It performs the same permitted search repeatedly, following the cursor the API
returns, and reports three numbers: how many calls it made, how many distinct customer records those
calls reached, and whether every one of them was allowed.

It reports **counts, never records** — the probe is not allowed to become a second way of reading
the data, which is the rule that keeps this a demonstration rather than the thing it describes.

Then run the audit observation and look at what the trail says about what you just did.

The flag is the number of distinct records one session obtained.
