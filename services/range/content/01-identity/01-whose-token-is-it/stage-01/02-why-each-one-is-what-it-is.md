# Why each is what it is

## Why A needs to be so wide

This is the part people hear as criticism and it is arithmetic.

A single credential that answers for **every** user must be able to reach **everything any of them
could reach**. If it cannot, some user's request fails. So the breadth is not carelessness in the
implementation — it is the requirement, and there is no narrower version of it.

In this lab that means membership in cedar *and* northwind, as a manager in both. When you arm the
control you are not introducing a bug. You are configuring a service account correctly.

That is what makes it worth an afternoon: **the vulnerability is the architecture working as
designed.**

## Why B is the dangerous one

Because it looks like C.

The tool takes a `user_id` parameter. The logs show per-user access. The code reads as though it
checks permissions per user. A review passes.

But the model produces that parameter, and anything the model produces is influenced by whatever the
model just read. The credential is still the wide one; the only thing standing between a customer's
ticket text and another tenant's data is a string the model chose.

> If a tool argument contains `user_id`, `organization_id`, `role` or `approved`, **the field should
> not exist.** Identity comes from a verified token, never from an argument.
