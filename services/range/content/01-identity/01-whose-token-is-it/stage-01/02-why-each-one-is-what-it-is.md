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

## Why C is not the end

C is the best of the classic three, and it is where this challenge ends up. It is still not good.

The agent is a **deputy**: it acts for alice. Under passthrough it holds everything alice can do —
read any of her tenant's customers, add notes, propose refunds — even when the task in front of it is
"where is order 2001?". That is **ambient authority**: present regardless of the task, and waiting
for the one ticket whose text steers the agent into using it.

And the audit trail cannot help afterwards. The row says alice, because the token said alice. Whether
alice made that request or her agent did is not recorded anywhere.

## What D changes, and what it needs

D keeps the user in the token and adds two things: the agent's name (`act`) and a narrow `scope` for
this task, for minutes. The effective permission becomes the **intersection** of what the user may
do, what the agent was registered for, and what the task needs.

It needs three things C does not, and each is a place it can quietly fail:

| D needs | If it is missing | Challenge |
|---|---|---|
| an issuer that mints narrow tokens, and no fallback to the user's own | passthrough again, by a switch | 1.5 |
| a resource server that **reads** the scope | a narrow token that narrows nothing | 1.6 |
| a scope decided by trusted code, not by the agent | the agent asks for everything | 1.7 |
| re-issued tokens that can only narrow | a chain that grows at every hop | 1.8 |
