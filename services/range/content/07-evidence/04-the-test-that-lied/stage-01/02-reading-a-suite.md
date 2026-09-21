# How to read somebody else's suite

You will be handed a test suite and asked whether it covers the thing. You will not have time to
understand the system it tests. Here is the order that finds the most in the least time.

## 1 · Read the names with the bodies covered

Just the names, top to bottom. You are sorting them into two piles:

- **Claims about a request.** *"A cross-tenant read returns 404."* Small, checkable, honest.
- **Claims about the world.** *"Bulk extraction is impossible." "Injection cannot escalate."
  "Secrets are never exposed."*

The second pile is your list. Not because those tests are bad — some of them are the best in the
suite — but because **a name that makes a universal claim can only ever be partly earned**, and the
distance between the claim and the assertion is the finding.

## 2 · For each one, write down what would make it fail

Literally list the conditions. Then ask: **is the property in the name on that list?**

```
Name:  "Secrets are never exposed"
Fails if:  this one endpoint returns a string matching this one pattern
On the list?  no — it covers one endpoint and one pattern
Honest name:  "This endpoint does not echo an API key"
```

That is a finding you can write in one line, and the fix is free.

## 3 · Look for assertions that prove the opposite of the name

This is the rare one, and it is worth the extra minute.

Sometimes a test carefully verifies that a mechanism works — correctly, thoroughly, with good
assertions — and that mechanism is precisely what makes the thing in the name possible. The test is
not weak. It is *rigorous*, and pointed backwards.

When you find one, the tell is that the assertion feels reassuring while you read it and the name
feels reassuring separately, and nobody has held the two side by side.

## 4 · Check which layer refused

A test that asserts "the request was refused" should say *by what*. A malformed request rejected at
schema validation never reaches the authorization code the test claims to cover — so the test would
pass with the authorization layer deleted.

Ask of any negative test: **would this still pass if the control it covers were removed?** If
nobody has tried it, nobody knows.

## 5 · And the question that closes the conversation

> *"Show me a test that failed when you removed the control it covers."*

Not a passing test. A **failing** one, deliberately produced. A negative test nobody has watched go
red is a decoration that has never been switched on, and this question finds that out politely in
about four seconds.

---

Now open Stage 03's source panels. One case from a real, passing suite. Read the name, then read
what it checks.

Then press the one button in the console. It makes the same permitted search over and over,
following the cursor the way the test proves the cursor can be followed, and counts what came back.
Hold that number next to the name while you read.
