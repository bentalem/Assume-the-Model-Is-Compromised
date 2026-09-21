# The checks, in order

"Is the signature valid" is one of seven questions, and it is the one everybody implements.

| Check | What it stops |
|---|---|
| Signature | a forged token |
| **Algorithm allowlist** | **`alg: none`, and HS256 confusion** |
| Issuer | a token from an identity provider the attacker controls |
| **Audience** | **a genuine token minted for a different service, replayed here** |
| `exp` / `nbf` | replay of an expired token |
| `typ` / `azp` | a refresh token or an ID token used as an access token |
| `kid` | key rotation |

The two in bold are the ones most often missing, for opposite reasons. The algorithm check is
missing because the library made it optional. The audience check is missing because nobody thought
to ask.

## `alg: none`

The JWT specification includes an algorithm called `none`, meaning "unsigned". It exists for tokens
that are protected some other way.

A verifier that reads `alg` from the header and does what it says will read `none`, skip the
signature check, and accept a token the attacker wrote entirely.

The fix is one line, and it is not "reject `none`" — it is **pin the algorithm**. Decide in advance
which algorithms you accept and refuse everything else, so a future header value nobody has thought
of is refused rather than dispatched on.
