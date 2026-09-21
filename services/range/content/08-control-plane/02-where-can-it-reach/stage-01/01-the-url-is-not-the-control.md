# The URL is not the control

Somebody asks for a small thing. The agent should be able to fetch the shipping carrier's tracking
page, or pull the PDF the customer linked, or read an internal wiki article when a ticket cites one.
All three are reasonable. All three are the same tool.

Here is what that tool looks like. **It is not in this repository**, and it is written out so you can
see the shape rather than imagine it:

```python
# NOT IN THIS LAB. This is the tool rule 7 of CLAUDE.md names, written down so you can read it.

ALLOWED_HOSTS = {"tracking.example-carrier.com", "wiki.internal"}

@router.get("/v1/fetch")
def fetch_reference(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise HTTPException(400, "host not allowed")
    return {"body": httpx.get(url, timeout=5).text[:4000]}
```

Review that and you will end up talking about the allowlist. Is the scheme check right. Does
`hostname` handle userinfo. What about a redirect to somewhere else, or a DNS name that resolves to
a private address, or a second lookup after the check has passed. Those are real questions and the
answers are all worth having.

They are also the wrong question to ask first.

## The question to ask first

> When that line executes, the request leaves a process. **What answers?**

That is a property of the network the process sits on, not of the code. The allowlist is a control
in the calling code, which means it holds exactly as long as the calling code is right. Network
placement is a control outside the calling code, which means it holds when the calling code is
wrong — and the calling code is eventually wrong, because a parser, a redirect handler and a DNS
resolver are three things you did not write.

So before you review the validation, draw the map. If the answer to *"what answers?"* is "nothing
interesting", the validation bug is a bug. If the answer is "the metadata service, the admin port on
the message broker, and the policy engine", the validation bug is an incident.

## What this lab has instead

Nothing. There is no operation here that accepts a URL, a host, a port or a path to fetch.

That is not an oversight and it is not modesty about scope. `CLAUDE.md` rule 7 says the model never
gets a generic tool — no SQL, shell, file, or unrestricted HTTP tool — and a URL parameter is the
HTTP one. Building 8.2 by adding the tool would mean shipping, in the lab that teaches people to
find it, the exact thing they are being taught to find. ADR-0004 settled the general form of this
question for a different capability and the reasoning carries: *arming a control the system already
has is a demonstration; adding a code path that does the dangerous thing is a vulnerability with a
comment above it.*

Press the first observation and check the claim rather than taking it. Seven operations, their
parameters and their request bodies. If one of them took a URL you would see it there.

The single outbound HTTP destination this API has is the policy engine, and its address is fixed
when the client object is built — read the third source panel in Stage 03. There is no URL to
validate because there is no URL to supply.

## The map, quoted

`compose.yaml` is not one of the directories the Range can read, so it is quoted here rather than
shown in a source panel. Six networks are declared, and **exactly one of them is not `internal`**:

```yaml
networks:
  edge:         { driver: bridge }                    # the only one with a route out
  app:          { driver: bridge, internal: true }
  policy:       { driver: bridge, internal: true }
  data:         { driver: bridge, internal: true }
  control:      { driver: bridge, internal: true }
  range_data:   { driver: bridge, internal: true }
```

And every service names the networks it joins. Collected, that is the whole topology of this lab in
six rows:

| Network | internal | Members |
|---|---|---|
| `edge` | no | keycloak, approval-portal, range |
| `app` | yes | keycloak, api, approval-portal, probe |
| `policy` | yes | opa-bundle-init, opa, api |
| `data` | yes | postgres, migrate, api, worker |
| `control` | yes | range, probe, docker-proxy |
| `range_data` | yes | postgres, range |

Two containers can open a socket to each other if and only if they share a row. That is the entire
rule, and everything in Stage 03 is derived from this table and nothing else.

Three consequences are worth reading off it before you go further.

- **Three services publish a host port** — keycloak, the approval portal and the Range — and they are exactly the three on `edge`. A port cannot be published from a network with no route out, so the list of things reachable from your laptop is decided by the same table.
- **The API publishes nothing**, and could not: every network it is attached to is `internal`. The verification suite therefore calls it from inside a container on `app`, which is also the path Onyx uses.
- **`policy` has three members and one of them is a job that exits.** The comment on that network says *"Nothing else may reach the policy decision point."* Check it against the table rather than believing it.

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
