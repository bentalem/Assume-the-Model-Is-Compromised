# More than “no rule matched”

Everyone agrees with deny by default. Ask what it covers and the agreement gets narrower.

Most people mean: **if no rule says yes, the answer is no.** That is the easy half, it is what the
policy language gives you for free, and it is not where systems fail.

The hard half is everything that is not an answer at all:

| Situation | A system that has thought about it | One that has not |
|---|---|---|
| No rule matched | deny | deny |
| The decision is undefined | deny | crash, or `None` treated as falsey — accidentally right |
| The response is malformed | deny | exception, and then whatever the handler does |
| `allow` came back as the string `"true"` | deny | **allow**, in most languages |
| Two rules conflict | deny | whichever the engine picked |
| The request timed out | deny | retry, then — what? |
| **The engine is unreachable** | **deny** | **this challenge** |

The last row is the one worth an afternoon, because it is the only one that happens **to every
system, eventually, without anybody attacking it.** Deployments, restarts, network partitions, a
full disk, a config reload that failed. The policy engine will be unavailable at some point.
