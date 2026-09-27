# The `user_id` pattern

Teams rarely build memory from scratch. They plug in a memory layer —
[Mem0](https://github.com/mem0ai/mem0), [Zep](https://arxiv.org/abs/2501.13956) and their peers — and
in normal use, **the application tells the memory layer which user it is acting for**, as a `user_id`
parameter, under one API key for the whole application.

That is the architecture the lab's article calls one credential answering for everyone, with
identity as an argument. If the wrong `user_id` is passed — by a bug, or by a component the model
influenced — the memory layer returns someone else's memories, correctly, as asked.

The store-level version of the same failure is older than agents. **ChatGPT, March 2023**: a bug in
a Redis client library showed some users other users' conversation titles. A shared store, a
boundary kept in application code, and one path where it was not kept. —
[The Hacker News](https://thehackernews.com/2023/03/openai-reveals-redis-bug-behind-chatgpt.html)

## What you are about to run

The observation reads the store with the Range's own **read-only** tokens — one per collection,
minted like the service's — and asks for what cedar's query would reach **with no filter at all**.
It is not a request through the service: the service always sends its filter. It is a measurement
of what the filter is holding up.
