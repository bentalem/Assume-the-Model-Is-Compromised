# The map was already written

Read straight off the table in Stage 01. Two containers can open a socket to each other if and only
if they share a network, so the reach of any service is the union of the rows it appears in.

| From | Its networks | Can open a socket to | Notably cannot reach |
|---|---|---|---|
| api | app, policy, data | keycloak, approval-portal, probe, opa, opa-bundle-init, postgres, migrate, worker | range, docker-proxy — and that is the complete list of what it cannot reach |
| range | edge, range_data, control | keycloak, approval-portal, postgres, probe, docker-proxy | api, opa, worker |
| worker | data | postgres, migrate, api | opa, keycloak, and everything on `edge` and `control` |
| approval-portal | edge, app | keycloak, range, api, probe | postgres, opa, worker |
| probe | app, control | api, keycloak, approval-portal, range, docker-proxy | postgres, opa |
| opa | policy | api, opa-bundle-init | everything else |

`migrate` and `opa-bundle-init` are one-shot jobs. They exit during startup, so for most of a
session they are rows on a diagram and not processes on a network. That distinction matters when
you read a topology: **a network member that is not running is not a thing you can reach, and a
network member that is not running today may be running during your next deploy.**

## So what would the tool have reached

The hypothetical `fetch_reference` from Stage 01 would have run inside the API container. Its blast
radius is the first row: eight other containers, including the database, the identity provider, the
worker and the policy decision point.

One of those answers without a credential. PostgreSQL wants a password. Keycloak wants a client and
a grant. The API wants a verified bearer token — including on `/internal`, which is a point worth
being exact about, since it is the endpoint an attacker would want most:

> `/internal` is excluded from the action document and never registered with Onyx, so the model has
> no route that names it. That is a real control against a model choosing to call it. It is **not**
> a control against a process that can already open a socket to `api:8000` — the thing that stops
> that request is the same token check every other route runs.

**OPA is the one that answers with nothing.** No authentication flag, no authorization flag, an
address of `0.0.0.0:8181`, and a network comment that says nothing else may reach it. Its protection
is the `policy` row and only the `policy` row.

So the honest answer to the flag is: the allowlist in `fetch_reference` was one control, and it
decided nothing about severity. What decided severity was that the process making the request sat on
`app`, `policy` and `data` at once. Take the same bug and put it in a service attached to one
internal network with one peer, and it is a defect. Put it in the API and it reads your
authorization policy.

## The checks that measure it, rather than asserting it

Both source panels above do the same thing, and neither of them reads `compose.yaml`. They open a
socket from inside a real container and report what answered. That difference is the whole value: a
topology is a claim about the runtime, and a claim about the runtime has to be measured in the
runtime.

- `V-17` runs inside the Range and fails if `api:8000` or `opa:8181` answers.
- `V-02` runs inside the approval portal — a service reachable from a browser — and fails if `postgres:5432` or `opa:8181` answers.

Both are worth copying, and the shape is the point: **a reachability check names the service doing
the reaching, not the service being reached.** "Nothing can get to the database" is unfalsifiable.
"From inside this container, this address does not answer" runs in seconds and fails loudly the
first time somebody attaches a service to one network too many — which is the usual way a route
appears, long before anyone would call it a finding.

## The worked example: a narrow path to something dangerous

Some of this lab's challenges need a container stopped and started again — 3.1 stops the policy
engine, and the proxy's list is written for three containers. The obvious implementation is to mount
`/var/run/docker.sock` into the Range and call the Docker API from Python, and the Range is the last
service in this repository that should hold that socket, because a process with the Docker socket is
root on the host.

It could have been done with an allowlist in `containers.py`: check the container name against a
tuple before sending the request. That is the `ALLOWED_HOSTS` pattern again, and it fails the same
way — it holds while `containers.py` is right.

What was built instead is a separate process. The Range's `DOCKER_PROXY_URL` points at an HAProxy
container that holds the socket, and that container's configuration is the whole of the authority:

```
acl allowed_container path_reg ^/(v[0-9.]+/)?containers/(supportpilot-opa|supportpilot-worker|supportpilot-api)/(stop|start|json)$

http-request deny deny_status 403 unless allowed_container
http-request deny deny_status 405 unless verb_ok
http-request deny deny_status 403 if { path_sub /exec }
```

Three paths, three container names, default deny. `postgres` is deliberately absent from the list.
Endpoints that do not exist yet are refused too, because a path this configuration has never heard
of does not match the allowlist — a new Docker API version brings new denials rather than new
surface.

Read the two `containers.py` panels together and the property is plain. The module sends the proxy
address plus a path built from a literal in `registry.py`, so nothing derived from a request reaches
it. And the proxy would refuse anything else regardless. Neither control is trusted alone — the same
two-layer rule the database work rests on, arriving somewhere with no database in sight.

**One honest detail, because a topology you have not read carefully is worse than none.** `control`
has three members, not two: the Range, the proxy, and the probe service. The probe is there so the
Range can ask it for a request, and the consequence is that the probe can also open a socket to the
proxy. Network placement did not make that path one-way and could not. What bounds it is the
allowlist — three verbs on three names is the same small thing whoever asks — which is precisely why
the narrowing has to live in the proxy rather than in the Range's own code.

## What to recommend, proportionately

1. **Draw the reach map before reviewing the parser.** For each process that makes outbound requests, list what shares a network with it. The list is the severity.
2. **Keep the egress allowlist.** It is cheap and it catches the ordinary case. Just stop describing it as the control.
3. **Put the dangerous capability behind a separate process with its own configuration.** The narrowing should survive a bug in the code that calls it.
4. **Assert reachability in a check that opens a socket.** A diagram, a policy document and a comment in a compose file are three ways of saying what you intended.
5. **Ask what on your internal network answers without a credential.** Metadata services, admin ports, brokers, policy engines and dashboards are the usual list, and the answer is normally longer than people expect.

## Take it to a review

1. **"Which of your processes can open a socket to your database, and how do you know?"** — a diagram is an intention; a check that tries it is a fact.
2. **"Show me the last SSRF fix you shipped. Was it a URL allowlist, or a network change?"** — if it is always the first one, nobody has drawn the map.
3. **"What on your internal network answers without a credential?"** — this is the question that converts a validation bug into an incident, or does not.
4. **"Which of your networks have a route out, and which services sit on them?"** — outbound reach and inbound exposure are usually decided by the same line of configuration.
5. **"When a service needs a dangerous capability, where does the narrowing live?"** — in the calling code, or in a separate process the calling code cannot talk round.
6. **"What does your verification suite assert about reachability, and when did it last fail?"** — a boundary check that has never gone red has never been tested.

Question 5 is the one that separates a team that has thought about this from one that has written it
down. The allowlist and the network are not alternatives; the network is what you are relying on
when the allowlist is wrong, and you should know which of the two you are actually depending on
before somebody finds out for you.
