# The Rules File Backdoor

**Cursor and GitHub Copilot, 2025.** Pillar Security showed that the rules files coding assistants
read on every run — `.cursorrules` and their equivalents — could carry instructions hidden in
invisible Unicode characters, making the assistant insert malicious code into what it wrote. The
files spread through public repositories and templates, and nobody reviews them the way they review
code. —
[Pillar Security](https://www.pillar.security/blog/new-vulnerability-in-github-copilot-and-cursor-how-hackers-can-weaponize-code-agents)

Two things made it work, and both are in this challenge:

- **Rules are obeyed, not read.** The assistant did not weigh the instruction against anything. It was a rule; rules are followed.
- **Nobody approved the change.** The rules file arrived with a repository. Whoever could write to it could change the agent.

In this lab the rule is proposed by the agent itself, after reading TKT-1001's internal note —
which is the shortest version of the same path: untrusted text in, standing instruction out.
