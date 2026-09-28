# The chain grew

## What your result proves

Unarmed:

```
token: none: the broker refused. refund-assistant re-exchanged status-helper's token for actions:read
status: 400    error_code: scope_exceeds_subject_token
```

refund-assistant may hold `actions:read`. It was refused anyway, because the rule the broker applies to a re-exchange is not *what may this agent hold* but *what was it handed*. The token it presented carried `orders:read`, and nothing more can come out of it.

Armed:

```
token: minted: act=refund-assistant; scope=actions:read     200    revealed: re_...
act:   {"sub":"refund-assistant","act":{"sub":"status-helper"}}
audit: action.read  allowed  agent: status-helper > refund-assistant
```

The value you submitted is a payment provider's reference, reached by a chain that started with a token for reading orders. Nobody in the chain was ever given `actions:read` for alice by anything that was supposed to decide it. The second hop decided it for itself.

Notice what did **not** go wrong. `act` nested correctly, the API read it into the chain, and the audit row names both agents in order. The trail is complete and honest — it records a chain that should not have existed. Attribution and attenuation are different properties, and this switch breaks only the second.

## Where the control lives

In one line of the broker's exchange (the first panel): the set a re-exchanged scope must fit inside. Secure, that is the presented token's own scope. Armed, it is the new agent's ceiling. Everything else in the branch — nesting `act`, keeping the user as `sub` — is the same in both states.

The second panel is the same rule in time: a re-exchanged token never outlives the one it was made from, whatever the switch says.

The third panel is the API's side. It reads nested `act` into the chain in delegation order, and it refuses a chain it cannot read rather than treating the token as the user's own. The API cannot tell, from a chain alone, whether each hop narrowed — only the issuer can check that, at the moment of exchange, against the token it was handed. That is why this control lives in the broker and not in the policy: the policy still applies the token's scope and the user's roles to every call, but it sees only the last token, not the one before it.

## What restoring fixes

Restoring puts the presented token's scope back as the bound. The sub-agent is refused again at the exchange.

Tokens already minted while it was armed remain valid until they expire. Because every re-exchanged token is capped at its parent's remaining lifetime, and the first token lived five minutes at most, that is never long.

## Take it to a review

1. **"When an agent hands work to a sub-agent, how does the sub-agent get a token?"** If the answer is "it has its own credentials", the chain is not delegation at all — the user is gone from it.
2. **"What is a re-issued token's scope computed from?"** The token presented, or the new holder? Only the first attenuates.
3. **"Can a re-issued token outlive the one it came from?"** If yes, a chain is a way to extend authority indefinitely.
4. **"Does the audit trail record every hop, or only the last holder?"** A trail naming only refund-assistant would make this chain look like refund-assistant acting for alice directly.

Question 2 is the one to ask. Most chain designs get attribution right, because it is visible. Attenuation is invisible until someone reads the line that computes the scope.

**Restore before you leave.** Until you do, any re-exchange can grow to the new agent's ceiling.
