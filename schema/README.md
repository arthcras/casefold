# Schema: one per kind of Relate file

The same Cypher works in Relate 1.0.1 and in Neo4j 5. `casefold/apply_schema.py` applies it to every built file and the viewer applies it in the browser.

| File | Schema | Kind of file |
|---|---|---|
| `register/<jurisdiction>.rl` (now `register/sectors.rl`) | `register.cypher` | sector register, no client data |
| `offices/<office>.rl` | `office.cypher` | office file, no names of clients or counterparties |
| `cases/<client>.rl` | `case.cypher` | client file |

Each file has three parts:

1. **Keys** (`IS UNIQUE`): work in Neo4j Community, Enterprise, Aura and Relate.
2. **Required fields and types** (`IS NOT NULL`, `:: TYPE`): Relate and Neo4j Enterprise or Aura. Neo4j Community refuses these; leave out part 2 there.
3. **Indexes** (range, text, fulltext): everywhere.

Vector indexes are created by `casefold/embed.py`, only when a local embedding model has filled `embedding`.

Relate checks a constraint against the data already in the file: a duplicate key or a wrong type stops the statement. `apply_schema.py` reports that per file and exits with 1.
