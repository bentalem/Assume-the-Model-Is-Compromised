# What you are about to run

## The attempt

The probe plays a compromised `status-helper`. It does everything by the book up to the last step:

1. It authenticates to the broker as `status-helper`, with the profile's own credential.
2. It exchanges alice's token for `orders:read` — exactly what the profile allows. The broker issues it.
3. It calls the API **directly**, not through the gateway, and asks for a customer.

Step 3 is the attack. Nothing about the token is forged, stolen or wrong. It is being used for something it does not cover.

## Where the decision happens

The API verifies the token (signature, issuer, audience, `act`), loads alice from the database, loads the customer from alice's own tenant, and asks the policy. For a delegated token, the policy input carries a fifth member beside subject, action, resource and context:

```json
"delegation": { "actor": "status-helper", "chain": ["status-helper"], "scopes": ["orders:read"] }
```

It is built from the verified token by the API itself — never from the request. The policy looks up the scope `customer.read` needs (`customers:read`, in the same `scopes.json` the broker uses) and checks whether the token carries it.

## The switch

**Remove the scope check from the live policy** is the same transform family as challenge 3.3: the real policy, read from the repository, with one named condition removed and OPA restarted. The broker is not touched. It keeps minting exactly the token it minted before.

## What to read

- The **token** column and the **last token** observation, before and after arming. If the token changed, the experiment is not about the API.
- The **audit** row for each attempt: the decision, the reason, and the policy version.

Run it unarmed first, and find the reason code the refusal was recorded with.
