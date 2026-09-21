# One argument

Row-level security in this system works by asking the database a question it can only answer if it
knows who is asking. Two settings carry the answer, and every policy reads them back through
`app.current_org()` and `app.current_user_id()`.

PostgreSQL has two ways to set them, and they differ by a single boolean:

```sql
SELECT set_config('app.organization_id', %s, true);   -- transaction-scoped
SELECT set_config('app.organization_id', %s, false);  -- session-scoped
```

`set_config(..., true)` is `SET LOCAL` with a bound parameter — which is what this API uses, so the
value never reaches the database as text it has to parse. `set_config(..., false)` is plain `SET`.

Both work. Both pass every test you would write for a single request. Both set the value, both
return the right rows, and for the whole length of one transaction **they are indistinguishable**.
