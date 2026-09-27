# How a proposal changed future instructions

## What your result proves

With normal approval enabled, the model's proposal was saved but did not become an active rule. With self-activation enabled, a new model proposal became active **without a recorded approver**.

Because active rules are selected for the organisation's future context, the change can affect other users, not just the conversation where the model proposed it.

This is why proposed rules are different from normal remembered facts. A rule changes the instructions the agent receives on later turns.

## Where approval is enforced

The model-facing `propose_rule` route accepts the proposed text only. The service records the proposer, organisation and a hash of that exact text. Approval happens through a separate runtime route restricted to authorised reviewers.

The reviewer must approve the hash they were shown and must not be the proposer. A database trigger checks the same separation of duties and enforces the legal state changes: proposal to approved or rejected, and active rule to retired. The rule's original text and approver cannot be rewritten after the decision.

This trigger also prevents a subtle database mistake. PostgreSQL can combine multiple permissive update policies. Policies are good at saying **which rows** may be changed, but they do not fully describe **which state changes** are legal. The trigger enforces the allowed transitions together.

## Closing the hole is not enough

Turning off self-activation stops new model proposals from becoming active immediately. It does not remove rules already created under the unsafe setting.

The Range's restore also retires active rules without a recorded approval. An authorised person can retire an approved rule separately. Retirement preserves the original approval record.

Even an active rule does not bypass the business API's own permissions or the separate refund approval flow.

## Take it to a review

- Can any model-facing action approve a rule or change its state directly?
- Must the reviewer approve the exact text rather than just a record ID?
- Are self-approval and illegal state changes blocked in the database too?
- How are active rules with no valid approval found and removed?
