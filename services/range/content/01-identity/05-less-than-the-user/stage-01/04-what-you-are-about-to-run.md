# What you are about to run

This challenge, and 1.6 to 1.8, need the broker running: `docker compose --profile delegation up -d`. The first observation tells you whether it is. Without it the console shows these controls as not running rather than guessing.

## The three requests

All three are alice, a support agent in cedar, asking for things she is allowed to see.

| Observation | Route | Token the API receives |
|---|---|---|
| status-helper reads alice's order | through the broker as `status-helper` | minted: `sub` alice, `act` status-helper, `scope` orders:read |
| status-helper reads a customer | through the broker as `status-helper` | none, if the broker does its job |
| alice reads the same customer | straight to the API | alice's own token: architecture C |

The second one is what an injected status-helper would try. alice may read that customer; status-helper was registered to answer questions about orders. Watch which component refuses it.

## What the rows show

Each result has a `token` column — how the token that reached the API was made — and a `revealed` column. The probe fills `revealed` with one declared field of the record, and only when the call succeeded. Unarmed, it should be empty.

The **last token** observation shows the claims of the most recent token the probe obtained or saw. It shows claim names and values only, never the token itself.

The **audit** observation is the one to read last. It shows `person` — always the human, because the human is still the actor — and `agent`, the delegation chain recorded beside them.

## One thing to be exact about

The profile in the gateway's path is not an authentication. Anyone calling the gateway already holds the user's whole token, and everything the gateway can do with it is narrower than what the caller already has. So choosing a profile in the URL can only ever take authority away. The attribution it records is as good as the agent platform that chose the URL; a platform that needs better than that authenticates as the profile, which is what the exchange endpoint requires.

## The switch

**Make the broker forward alice's own token** is a real configuration: passthrough mode, the setting somebody turns on when the narrowed token breaks a feature and a release is due. The gateway still exists, still takes a profile in its path, and still answers. It just stops narrowing.

Record all three results unarmed first. The finding is partly what changes, and partly what the trail stops being able to tell you.
