# Container proxy

Three challenges need a container stopped and started again — the policy engine, the worker, the
API. The obvious way to do that is to mount `/var/run/docker.sock` into the Range.

Do not mount the socket.

The Docker socket is root on the host. A service holding it can start a privileged container, mount
the host filesystem, and read every secret in this repository. That is not a smaller version of the
authority the Range needs; it is unbounded authority, handed to the one service in this lab whose
whole job is to break things.

So the Range gets a proxy instead. It is a normal HAProxy image with a configuration that:

* permits `POST /containers/<name>/stop`, `POST /containers/<name>/start` and
  `GET /containers/<name>/json`, and nothing else;
* permits them only for the container names listed in `ALLOWED` below, which is a closed set given
  at deploy time, not a parameter the Range can supply;
* refuses `exec`, `images`, `volumes`, `networks`, `build`, and every other path, including ones
  added by a future Docker API version — the default is deny, and new endpoints are new denials.

The result is that the worst thing a compromised Range can do through this path is restart three
containers in a local lab, which is also the best thing it can do, which is the point.

`V-17` asserts the Range cannot reach the API, and the proxy's allowlist is asserted by its own
smoke test rather than by reading this file.
