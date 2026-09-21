# Where the field is removed

## Where the field is actually removed

This matters, because there are three places it could happen and two of them are wrong.

| Where | Problem |
|---|---|
| The query | The field list is now compiled into SQL. A policy change needs a code change |
| The response model | The data was already loaded, and already in the process. Better, still late |
| **The API, between the query and the response** | The policy said which fields; trusted code removes the rest |

The lab does the third. The decision lives in policy, where it can change under review; the
enforcement lives in trusted code, where it cannot be argued with.

And note what that means for the agent in front of it. The withheld field **never reaches the
model's context at all.** Not hidden, not filtered out of the answer — never loaded into the
conversation. That distinction is the whole of "post-filtering is not access control".

## What you are about to do

Two requests, through the API, with two real people's tokens. Same endpoint, same customer, both
permitted.

Compare the field lists. The difference is the control.
