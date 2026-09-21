# Who, not what

Three stages get collapsed into one word, and the collapse is where systems fail.

| | The question | Where the answer comes from |
|---|---|---|
| **Authentication** | is this token real? | a cryptographic signature |
| **Identification** | who does it name? | the `sub` claim |
| **Authorization attributes** | what is this person? | **the server** |

The first two genuinely are the token's job. The third is not, and it is the one that ends up in
there anyway — because the roles are right there in the payload, and reading them is one line
shorter than loading them.

```python
# One line. Fast. Wrong.
roles = token["realm_access"]["roles"]

# Three lines, a round trip, correct.
subject = memberships.load_subject(token.subject, token.authentication_level)
```

## What a token actually is

**A snapshot, taken at login.**

Revoke a role at 10:00 and a token minted at 09:58 still carries it. It will keep carrying it until
it expires, which is however long the identity provider was configured to allow — five minutes, an
hour, eight hours, and in one memorable case a refresh token valid for thirty days.

For that whole window, a system that reads roles from the token is enforcing a decision that was
reversed.

> **Roles in a token are cached authorization with no invalidation.** Nobody would design that on
> purpose; it arrives by reading a field that was already there.
