# Obligations

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

The agent gets a useful record with one field missing. Nobody had to choose between the two bad
options, and nobody had to create a workaround.

## Why this is the feature people do not know exists

Because every tutorial for every policy engine returns `allow: true`. Obligations are in the
specifications, they are in the products, and they are almost never in the examples — so systems get
built with a boolean, and the boolean forces the choice above.

When you review an agent's authorization layer, this is a genuinely useful question:

> **What can your policy return, other than yes and no?**

If the answer is "nothing", you now know why their sensitive-data handling is all-or-nothing, and
you know it without reading any of their code.
