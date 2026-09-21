# You cannot know

Your worker calls the payment provider. Thirty seconds later the connection times out.

**Did the money move?**

You do not know. Three things are equally consistent with what you observed:

1. The request never arrived. Nothing happened.
2. The request arrived, the refund was issued, and the **response** was lost.
3. The request arrived and is still being processed.

And the decision you have to make right now is whether to retry.

- **Retry, and it was case 2** → you have refunded twice.
- **Do not retry, and it was case 1** → the customer is still waiting, and eventually somebody
  refunds manually. Possibly twice.

There is no answer that is safe *by itself*. This is not a hard problem because people are careless;
it is hard because the information genuinely is not there.

## So stop trying to know

The whole trick is to give up on finding out what happened, and instead make **the second attempt
harmless**.

> **Idempotency: performing the same operation twice has the same effect as performing it once.**

If that holds, the timeout stops being a dilemma. Retry. Retry ten times. If the first call landed,
the rest change nothing.
