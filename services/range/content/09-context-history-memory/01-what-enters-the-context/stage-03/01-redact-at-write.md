# Why the secret reached the next context

The runtime saves a tool result through `POST /v1/sessions/{session_id}/turns`. With the secret filter on, the service replaces recognised credentials **before** saving the turn.

Context assembly later loads that saved turn. It does not scan every stored turn again. If the filter was off during the write, the unredacted value can still be there after you restore the setting.

Long-term memory is different: the service refuses a recognised credential instead of keeping a redacted memory.

The filter only finds secret formats it recognises. It is not a reason to give the model more data or more tools than it needs.

## Take it to a review

- Where does the runtime save tool output? Is filtering done before storage?
- Which older turns were written while filtering was disabled?
- Can you trace which context blocks included those turns?
- What can the model do with the data if filtering misses it?
