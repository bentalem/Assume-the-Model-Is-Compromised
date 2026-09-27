# Check history permissions when it is used again

Each saved turn records `authz`: the user's roles when that turn was written. These roles come from the verified principal, not from the model's input.

Before replay, context assembly gets the user's **current roles** from the core database. It leaves out tool and assistant turns if any role recorded at write time has been lost. The context log says what was omitted and why.

This rule is intentionally broad. It may hide a turn even when the lost role did not matter for that particular result. The current implementation does not track the exact permissions for every field fetched by every tool.

When revalidation is disabled, the old result can enter the context despite the role change.

## Take it to a review

- Does history record the permissions under which each tool result was fetched?
- Does the runtime check those permissions again before replay?
- What happens when access to one record changes but the user's role does not?
- Can an investigator find the contexts that included an old result?
