# What you are about to run

## The chain

The probe plays two agents, each authenticating to the broker with its own profile credential:

1. **status-helper** exchanges alice's token for `orders:read`. Its ceiling allows exactly that; the broker issues it.
2. It hands that token to a sub-agent, **refund-assistant**, whose own ceiling is `orders:read`, `refunds:propose` and `actions:read`.
3. refund-assistant re-exchanges the token it was handed and asks for `actions:read`.
4. If it gets a token, it reads the status of one of alice's refunds with it.

Step 3 asks for something refund-assistant may hold, but that the token it was handed does not carry. Which of those two facts the broker checks is the whole challenge.

## The switch

**Let a re-exchanged token take its scope from the new agent** is a real configuration: re-exchange that recomputes scope from the new holder's registration, because "that is what the agent is allowed to do". The broker still nests `act`, so the trail still shows the chain. The chain just grows on the way.

## What to read

- The **status** and **error code** unarmed. Note which rule the broker quotes.
- The **last token** armed. The `act` claim is nested; read it from the outside in, and write down the chain it describes.
- The **agent** column on the audit row for the action read. Compare it with what you wrote down.

Record the unarmed result first. Then ask, for the armed run: which of the two agents decided how much the final token could do?
