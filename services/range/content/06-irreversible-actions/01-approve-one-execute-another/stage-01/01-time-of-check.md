# Time of check

Somebody says *"the refund was approved"*. Ask what that sentence is about.

**"A refund"?** Then it is a category, and an approval of a category is a standing permission to
issue refunds — which nobody intends and everybody implements.

**"That refund"?** Then something has to pin down *which*, and pin it down in a way that cannot
drift between the moment of approval and the moment of execution. Those two moments are seconds
apart in the happy case and hours apart in the interesting one.

> **Approving an action is not a control. Approving a payload is.**

## Time of check, time of use

The gap is the oldest shape in security. A value is checked, and then used, and something happens in
between.

```
09:14:02   propose    amount 45.00
09:14:40   approve    "yes, 45.00 is reasonable"
09:14:41   ...
09:18:33   execute    amount ????
```

If the thing that executes reads the amount fresh from a row that anyone could have updated, the
approval covered a number that no longer exists. Nobody forged an approval. The approval is genuine,
recorded, attributable — and it is about a different payload.
