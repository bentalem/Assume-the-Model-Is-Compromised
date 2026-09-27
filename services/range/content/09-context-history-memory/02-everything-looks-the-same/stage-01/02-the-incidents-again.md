# The same two incidents, from the other side

9.1 read Slack AI and EchoLeak as a question about what enters the context. Read them again as a
question about what the model could tell apart once it was there.

**Slack AI, 2024.** The attacker's public message and the victim's private API key arrived in the
same context, from retrieval, looking like the same kind of thing — two search results. —
[PromptArmor](https://www.promptarmor.com/resources/data-exfiltration-from-slack-ai-via-indirect-prompt-injection)

**EchoLeak, 2025.** An email from outside the organisation and internal documents arrived together
as retrieved content for an unrelated question. —
[The Hacker News](https://thehackernews.com/2025/06/zero-click-ai-vulnerability-exposes.html)

Suppose both products had labelled every retrieved item with its source. The model would have read
"from a public channel" or "from an external email" — and then the instruction. Whether it followed
the instruction would have been down to the model on the day.

What would have stopped both: the answer not being able to carry data to an attacker's URL, whatever
the model decided. That is a control on what the agent can do, not on what it reads.
