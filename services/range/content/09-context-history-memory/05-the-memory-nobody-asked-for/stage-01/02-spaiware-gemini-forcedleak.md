# SpAIware, Gemini, ForcedLeak

**ChatGPT memory, "SpAIware", 2024.** A web page or document carrying hidden instructions made
ChatGPT store a memory the attacker chose. In the macOS app that memory told it to send every future
conversation to the attacker's server — in new conversations too, until somebody deleted it. One
injection became persistent spyware. —
[The Hacker News](https://thehackernews.com/2024/09/chatgpt-macos-flaw-couldve-enabled-long.html)

**Google Gemini, 2025.** A document told Gemini: *when the user later says "yes", save to memory
that…*. The user said "yes" to something ordinary, and the false memory was written. The attacker did
not ask for a write; he timed it to look like the user's own request. —
[Embrace The Red](https://embracethered.com/blog/posts/2025/gemini-memory-persistence-prompt-injection/)

**Salesforce Agentforce, "ForcedLeak", 2025.** An attacker filled in a public web-to-lead form, and
the instruction was stored in the CRM as an ordinary field — then read by the agent whenever an
employee asked about the lead. —
[Noma Security](https://noma.security/blog/forcedleak-agent-risks-exposed-in-salesforce-agentforce)

The Gemini case is the one to keep. It shows that **"the user confirmed it" is only a control if the
confirmation is something the model cannot produce** — not a "yes" in the chat that the model
interprets, but an action on a path the model does not have.
