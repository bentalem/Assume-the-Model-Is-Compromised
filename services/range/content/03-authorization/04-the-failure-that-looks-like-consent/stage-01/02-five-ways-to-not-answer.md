# Five ways to not answer

## Five ways to not get an answer

Open the client source below and count the returns. A decision point can fail to answer because:

1. it **timed out** — the request went out, nothing came back in time
2. it was **unreachable** — no connection at all
3. it answered with a **bad status** — it is up, and the evaluation itself failed
4. it answered with something **unparseable** — a body that is not JSON
5. it answered **200 with no decision in it** — the path the API asked for is undefined

Numbers 3, 4 and 5 are the ones people forget, because they all begin with *the engine answered*.
Monitoring that watches for "is the policy service up" sees a healthy service in all three.

Number 5 deserves its own sentence. An undefined result is not an empty result and it is certainly
not a denial — it is **the absence of an opinion**. What a system does with a missing opinion is the
single most revealing line in any authorization client, and you should go and read that line in
every codebase you are ever asked to review.

## What you are about to do

Three of those five you can cause from this console, and you should do them one at a time:

1. **Stop the engine.** Unreachable. The obvious one.
2. **Make evaluation error.** The bundle loads, two rules collide, OPA returns a 500.
3. **Move the decision out from under the API's feet.** OPA is healthy, answers 200, and the thing
   the API asked for is not there.

For each one, make the same completely ordinary request — alice reading her own order, a call that
is permitted and boring — and record two numbers and one word:

- the **HTTP status** the caller received
- the **reason** in the audit trail
- whether the engine was **running**

Then compare the three rows. Two of them will agree. The third is the challenge.
