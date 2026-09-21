# The URL is not the control

Somebody asks for a small thing. The agent should be able to fetch the shipping carrier's tracking
page, or pull the PDF the customer linked, or read an internal wiki article when a ticket cites one.
All three are reasonable. All three are the same tool.

Here is what that tool looks like. **It is not in this repository**, and it is written out so you can
see the shape rather than imagine it:

```python
# NOT IN THIS LAB. This is the tool this repository refuses to build, written down so you can read it.

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
