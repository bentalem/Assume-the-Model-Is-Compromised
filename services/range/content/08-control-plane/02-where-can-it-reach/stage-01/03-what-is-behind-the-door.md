# What is behind the door

## What is behind the door

One more thing to establish before Stage 03, because it decides how bad the hypothetical is.

OPA is started like this:

```yaml
command: ["run", "--server", "--addr=0.0.0.0:8181",
          "--log-level=info", "--set=decision_logs.console=true", "/policy"]
```

There is no `--authentication` flag and no `--authorization` flag. Whatever can open a socket to
`opa:8181` can use its API. PostgreSQL wants a password; the policy decision point does not. Its
only protection is that almost nothing can reach it.

Which is a perfectly good control. It is just not the control anyone would have named if you asked
them what protects the policy engine.

## Your job

1. Take the table above and work out what a process **inside the API container** can reach.
2. Do the same for the Range, and check your answer against V-17 in Stage 03.
3. Say what the hypothetical `fetch_reference` tool would have been able to read, which service would have answered it with no credential, and which of the two controls — the allowlist or the network — was doing the real work.
