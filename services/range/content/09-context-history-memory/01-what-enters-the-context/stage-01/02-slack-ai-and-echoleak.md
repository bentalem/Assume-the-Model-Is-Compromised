# Slack AI and EchoLeak

Two incidents, one path.

**Slack AI, 2024.** An attacker posted a message in a public channel. When a victim later asked
Slack AI a question, retrieval brought the attacker's message into the context *alongside an API key
from the victim's private channel*, and the injected text made the answer carry a link that sent
the key away. The attacker was never in the private channel. —
[PromptArmor](https://www.promptarmor.com/resources/data-exfiltration-from-slack-ai-via-indirect-prompt-injection)

**Microsoft 365 Copilot, "EchoLeak", 2025 (CVE-2025-32711).** Zero-click: the attacker sent an email.
When the user later asked Copilot something unrelated, retrieval pulled the email into context
together with internal data, and the data left through an image URL. —
[The Hacker News](https://thehackernews.com/2025/06/zero-click-ai-vulnerability-exposes.html)

In both, the secret was not stolen from a database. It was **put in front of the model** by the
system's own context assembly, next to text that told the model what to do with it. The attacker's
part was only the second half.

The lesson for a store is narrow and it is enough: a secret that never reaches the context cannot be
sent anywhere from there. Everything else is a question about what the model does, and you do not
get to decide that.
