# Output is input

Most of this track is about text arriving at a model. This one is about text leaving it.

An agent's answer is not the end of anything. It gets written into a ticket, pasted into a chat
client, stored in a CRM field, and — the case this challenge is about — **rendered into a page a
human being reads before authorising money to move.**

At that moment the model's output is somebody else's input, and the rules of that somebody else
apply. A browser's rule is that angle brackets are markup.

## The surface in this lab

It is not hypothetical and it is not a mock. `services/approval-portal/` is a running service whose
entire job is to show an approver what they are about to approve:

```
alice proposes a refund        ->  app.action_requests, with a frozen payload
fiona opens /actions/<id>      ->  the portal fetches it from the API
the portal renders it          ->  amount, currency, reason, the canonical payload, the hash
fiona clicks approve           ->  a decision bound to that hash
```

Nine labelled rows and a payload block, straight into an f-string. If any of them could carry
markup, the page a human is asked to trust is a page an attacker helped write — and the consequence
is not a stolen cookie, it is a signature on the wrong number.
