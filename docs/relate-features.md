# Relate features in Casefold

An inventory of Relate v1.1.0 (from its README, `relate --help` and `relate agent-context`), and what Casefold does with each feature.
"Live" means you can run it yourself in the viewer: click **Relate inside** in the top bar. Every card there runs its Cypher in the page, on Relate compiled to WebAssembly, and shows the result with Relate's own timings.

## Used

| Relate feature | What Casefold uses it for | Where | Live |
|---|---|---|---|
| **Single-file store (`.rl`)** | One file per client, per office, per law version and language, for the sector register and for long-term memory: 52 files after `run.sh` (the viewer loads 51 of them; long-term memory stays out of the page). The file is the record: it isolates a client, goes to an auditor as one unit and is deleted as one unit. | `cases/`, `offices/`, `register/`, `laws/`, `memory/` | 01 |
| **WebAssembly build** (`RelateDb.execute`, `executeScript`) | The viewer: each file is replayed into Relate in the browser and every answer is a Cypher query in the page. No server. | `web/index.html` | all |
| **Schema DDL, enforced** (UNIQUE, NODE KEY, NOT NULL incl. on relationships, `IS :: TYPE`) | One schema per kind of file. Relate checks every constraint against the data already in the file; a violating write is refused and leaves nothing behind. It caught a real bug (two agent sessions with the same id). | `schema/*.cypher`, `casefold/apply_schema.py` | 02, *Try to break it* |
| **Range and text indexes** | Keys of every node kind; party and counterparty names. | `schema/` | 02 |
| **Quantified path patterns** `((a)-[:OWNS]->(b)){1,6}` | The ownership chain: every top owner, the hops, and the effective share multiplied along the path. | viewer, queries | 03 |
| **Path selectors** (`SHORTEST 1`) | The shortest ownership route from an owner to the client, as evidence for a UBO ground. | viewer | 04 |
| **Temporal modelling in Cypher** (dates, `REPLACED_BY`) | A duty rests on an article per legal regime with `valid_from` / `valid_to`; on 10 July 2027 each Wwft article is replaced by its AMLR successor. The same query answers for any date. | `build_duties.py`, testing query | 05 |
| **Full-text indexes** (`db.index.fulltext.queryNodes`) | Proposes the section of a procedure that covers a duty when the text cites no article; also law articles and documents. | viewer, `queries/` | 06 |
| **Vector indexes with `SEARCH`, then graph matching** | In the browser: every source section is embedded in the page (no text leaves it) and the nearest sections are found by meaning, then filtered by a graph match. On disk: `embed.py` and `semantic.py` with a local sentence model. | viewer, `casefold/embed.py`, `semantic.py` | 07 |
| **Hybrid full-text + vector** | In the testing table, every proposal from the full-text index is checked by the vector index ("vector index agrees"). | viewer | testing |
| **`EXISTS { }` subqueries** | Required documents that are missing; per-duty collections. | `queries/` | — |
| **`PROFILE` / `EXPLAIN`** | The testing query profiled: operators, rows, db hits. The AI agent's read tool runs every generated query through `EXPLAIN` first: a syntax error comes back to the model, and Relate's warnings (an unknown label, type or property) are returned with the rows, so an empty result is not taken as "not in the file". | viewer | 08 |
| **Per-phase timings** (parse, plan, execute) | Shown under every live answer. | viewer | all |
| **Parameterised write scripts** | Reading in a law, guidance, a procedure or a case, and confirming a citation by hand, are Cypher scripts with parameters, in the page. | viewer | 09 |
| **CLI `query`** with `--read-only`, `--json`/`--csv`, `--fetch-params` | Building every file and testing 28 clients and 14 offices against an independent Python implementation. | `run.sh`, `casefold/*.py` | — |
| **`relate query --read-only` behind an MCP server** | The grounded AI agent: `casefold/agent_mcp.py` is Casefold's own MCP server on one client file. Its only evidence tool runs `relate query --read-only`; every node returned is logged as read, and a claim citing a node it never read is marked ungrounded. | `casefold/agent_mcp.py`, `agent_demo.py` | — |
| **`relate serve --mcp`** | Relate's own MCP server (tool *Read Cypher*), for plain read-only access to a client file without memory or grounding checks. Tested with stdio. | README | — |
| **`relate clone --to-snapshot-format json`** | The auditor hand-over: a readable JSON snapshot of one client file that Relate still opens as a database. | `casefold/handover.py` | — |
| **`relate info --json`** | The hand-over manifest: counts, every constraint and index, format, commit; with the sha256 of the file. | `casefold/handover.py` | — |
| **`relate pull`** | The rulebook slice from a central Neo4j database (same Cypher schema). Supported (`build_case.py --pulled`), not part of the demo run. | `neo4j/`, `build_case.py` | — |

## Not used, and why

| Relate feature | Why not |
|---|---|
| `relate push` | The files are the records; nothing goes back to a central database. |
| `serve --http` / `--bolt` | No server is needed; agents use MCP over stdio. |
| OPFS persistence in the browser | By design the viewer keeps client data in memory only; nothing stays behind in the browser. |
| Markdown snapshot format | Its file names are derived from a key property; JSON is the hand-over format here. |
| Geospatial point indexes, LOAD CSV | No locations; the input is JSON. |
| Python/Arrow, Java, Go, Swift bindings | The CLI and WebAssembly cover the demo. |
