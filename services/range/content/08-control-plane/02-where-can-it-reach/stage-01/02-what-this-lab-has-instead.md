# What this lab has instead

## What this lab has instead

Nothing. There is no operation here that accepts a URL, a host, a port or a path to fetch.

That is not an oversight and it is not modesty about scope. This lab's first rule is that the model
never gets a generic tool — no SQL, shell, file, or unrestricted HTTP tool — and a URL parameter is
the HTTP one. Building this challenge by adding the tool would mean shipping, in the lab that
teaches people to find it, the exact thing they are being taught to find.

The line the Range holds to everywhere: *arming a control the system already has is a
demonstration; adding a code path that does the dangerous thing is a vulnerability with a comment
above it.*

Press the first observation and check the claim rather than taking it. Seven operations, their
parameters and their request bodies. If one of them took a URL you would see it there.

The API makes outbound HTTP requests to exactly two places — the policy decision point, and
Keycloak's JWKS endpoint — and both addresses are configuration, fixed when the client object is
built. Read the third source panel in Stage 03. There is no URL to validate because there is no URL
to supply.

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
