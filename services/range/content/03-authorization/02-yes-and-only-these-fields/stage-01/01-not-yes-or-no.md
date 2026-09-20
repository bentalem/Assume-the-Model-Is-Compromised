# The answer is not yes or no

Most people picture authorization as a gate. The request arrives, something decides, and the request
either passes or does not.

That model forces a choice nobody wants to make.

A support agent is working a ticket for a customer whose record is marked sensitive — a public
figure, a colleague, someone under a protection order. They need the name, the team, and the open
ticket count to do their job. They do not need the home address.

With a gate, there are two options:

- **Refuse.** The agent cannot work the ticket. Someone senior gets interrupted, or the customer
  waits, and within a month there is a shared account that is never marked sensitive.
- **Allow.** The agent gets the whole record, address included, because the gate has no vocabulary
  for "most of it".

Both are bad, and the second is what almost always ships — because the first stops people working,
and a control that stops people working gets removed.

## The third answer

A policy engine can return more than a boolean. It can return **an allow with conditions attached**:

```rego
decision := allow_with("restricted_customer_minimal_fields", {
    "allowed_fields": customer_fields_restricted,
}) if {
    input.action == "customer.read"
    in_tenant
    any_role(read_roles)
    input.resource.sensitivity == "restricted"
    not any_role({"support_manager", "auditor"})
}
```

That is called an **obligation**: *yes, and only these fields.* The decision is not a gate; it is an
instruction that the calling code has to carry out.

The agent gets a useful record. The address is not in it. Nobody had to choose between the two bad
options, and nobody had to create a workaround.

## Why this is the feature people do not know exists

Because every tutorial for every policy engine returns `allow: true`. Obligations are in the
specifications, they are in the products, and they are almost never in the examples — so systems get
built with a boolean, and the boolean forces the choice above.

When you review an agent's authorization layer, this is a genuinely useful question:

> **What can your policy return, other than yes and no?**

If the answer is "nothing", you now know why their sensitive-data handling is all-or-nothing, and
you know it without reading any of their code.

## Where the field is actually removed

This matters, because there are three places it could happen and two of them are wrong.

| Where | Problem |
|---|---|
| The query | The field list is now compiled into SQL. A policy change needs a code change |
| The response model | The data was already loaded, and already in the process. Better, still late |
| **The API, between the query and the response** | The policy said which fields; trusted code removes the rest |

The lab does the third. The decision lives in policy, where it can change under review; the
enforcement lives in trusted code, where it cannot be argued with.

And note what that means for the agent in front of it: **the address never reaches the model's
context at all.** Not hidden, not filtered in the answer — never loaded into the conversation. That
distinction is the whole of "post-filtering is not access control".

## What you are about to do

Two requests, through the API, with two real people's tokens. Same endpoint, same customer, both
permitted.

Compare the field lists. The difference is the control.
