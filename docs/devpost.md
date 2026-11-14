# Casefold — KYC compliance as connected context, on Relate

**Tagline:** The law, a company's procedure and the cases where it went wrong, in one Relate graph, so an office sees per duty what it must do, what it does, and what changes when the law changes.

## Try it out
- **Prototype in the browser (GitHub Pages):** <https://OWNER.github.io/casefold/>. Press *+ New client from documents*, then *Use the example documents* → *Read into the graph* → *Confirm all*. The *Relate inside* button shows each Relate feature live.
- **Code:** <GitHub link>. `bash run.sh` rebuilds every Relate file and runs all tests in about 30 seconds. The same viewer runs locally: `cd web && python3 -m http.server 8000`.
- **Video:** <YouTube/Vimeo link> (1:59).

## Inspiration
Compliance officers at banks, payment institutions and trust offices answer the same questions every day. Which rule applies to this client? Who is the beneficial owner? Does our procedure cover every duty? What changes when the EU's new AML regulation (AMLR) replaces the Dutch Wwft on 10 July 2027? The answers sit in PDFs of laws, the supervisor's guidance, an internal procedure and a list of fines. Those are four documents that never point at each other. The fines tell the story: in 2026 DNB fined a payment institution €2.66m because its transaction monitoring missed transactions for two years. The duty was in the law and in the procedure, but nobody could see the gap.

These are questions about connections, so they belong in a graph. Client data cannot go into one shared database, though: a client file belongs to one client, goes to an auditor, and must be deleted when the retention period ends. Relate, an embedded graph database that keeps a graph in a single file, fits exactly.

## What it does
- **Reads the law into the graph.** The official Wwft (XML from wetten.overheid.nl), the AMLR in Dutch and English (EUR-Lex PDFs) and the Sanctiewet each become a Relate file: law → article → paragraph → point, verbatim, with the sha256 of the source. Scans go through Tesseract.
- **Builds duties that move with the law.** Each duty (report unusual transactions, ongoing monitoring, record keeping, …) rests on an article per legal regime, with dates. On 10 July 2027 the Wwft article is `REPLACED_BY` its AMLR successor. Every AMLR article number is checked against its official heading. Where a parameter changes, a successor duty replaces the old one (customer due diligence for an occasional transaction: from €15,000 to €10,000).
- **Takes any source.** In the browser you drop in a law, the supervisor's guidance, a company procedure or an enforcement case (PDF, XML or text). It is cut into sections, and every citation it contains ("artikel 3, tweede lid, Wwft", "Rtsw art. 3", "AMLR art. 69") becomes a `CITES` edge to the article a duty rests on.
- **Tests a company against the law.** For the fictitious payment institution *Voorbeeld Betaal B.V.*, one Cypher query lists per duty: the article valid on the chosen date, the section of the procedure that cites it, the supervisor's guidance, and published enforcement cases on the same duty (DNB vs bunq, CCV, ABN AMRO and Coinbase; the OM settlement with ABN AMRO). Where the procedure cites no article, Relate's full-text index proposes the section that covers the duty. The officer confirms it with one click, and that is stored as a citation confirmed by hand. Switch the date to 10 July 2027 and the same procedure drops from 8 covered duties to 1, because it still cites the Wwft. The change of law becomes a work list.
- **Starts from the client's own documents, in the browser.** Press *New client from documents*, then add the client's structure chart and scans. The chart, a vector PDF, is read box by box and line by line: boxes are the parties, lines are ownership or control, and the label gives the percentage, "no votes" or "veto". Scans are read with OCR, using Tesseract compiled to WebAssembly in the page. Every fact becomes a proposal that points to the spot in the chart where it is drawn. Only what the compliance officer confirms enters the client's graph. The review follows at once:
  - the documents still to request, each with its article;
  - the beneficial owners;
  - the finding that Lina Brouwer (16% of the shares, plus a veto) is missing from the UBO register;
  - a request to the client, ready to send.

  The same steps run on the command line (`new_client.py`, `structure_chart.py`), and a test checks that the result equals the hand-built client.
- **Keeps client files apart.** Each client is its own Relate file: owners and the ownership chain, documents (OCR passages with page and position), transactions, the client's own customers (KYCC), and the slice of law that applies. The beneficial owner is determined ground by ground, under the rule of the office's supervisor, with the article for every ground. The office has its own file with its own duties and evidence, and sees its clients only by key, without names.
- **Remembers how it answered.** Answers are stored as steps that cite the nodes they rest on. An AI agent works over MCP on one client file. Every node it reads is recorded, so a claim that cites something it never read is marked ungrounded. Approved patterns go to a shared long-term memory file without client data.

Scope: the Netherlands, the 14 sectors under the Wwft that DNB or the AFM supervise, with FIU-Nederland. The demo has 28 test clients, 14 test offices, and a client built from its own documents.

**No AI at run time.** Every answer in the viewer is a Cypher query over Relate files built from the law texts and the client's documents. An AI agent is optional: it reads only one client file over MCP, and every claim must cite the nodes it read.

## How we built it
- **Relate v1.0.1 in single-file mode**: one `.rl` file per client, per office, for the sector register, per law version and language, and for long-term memory. Each file is the record. It isolates a client, moves to an auditor as one unit, is deleted as one unit, and needs no server. The files are committed, so the judges can open them with the CLI.
- **The same files in three places:** the Relate CLI for the build and the tests; **Relate in WebAssembly** in the viewer, which replays the files into an in-memory graph and runs every answer as Cypher in the page; and an MCP server (`casefold/agent_mcp.py`, on `relate query --read-only`) for an AI agent on one client file.
- **Relate features, each one live in the viewer.** The **Relate inside** button opens nine cards that run in the page with Relate's own timings:
  - one graph file per record (51 `.rl` files);
  - Neo4j 5 schema DDL that Relate enforces: keys, required properties, types, also on relationships. Press *Try to break it* and Relate refuses a duplicate sector, leaving nothing behind. The schema also found a real bug: two agent sessions in the same second got the same id;
  - quantified path patterns `((a)-[:OWNS]->(b)){1,6}` and `SHORTEST 1` for the ownership chain and the effective share;
  - dated articles with `REPLACED_BY` for the law that changes;
  - a full-text index and a **vector index with `SEARCH`** on every section of every source, followed by a graph match. Embeddings are computed in the page, so no text leaves the browser. In the testing table the two run as a hybrid: the vector index checks each full-text proposal;
  - `PROFILE` of the testing query;
  - parameterised write scripts for reading in sources and confirming citations.
- **Relate on the command line:**
  - `relate query --read-only --json --fetch-params` builds and tests every file;
  - an MCP server on `relate query --read-only` gives an AI agent the client file as its only evidence, and Relate's own `relate serve --mcp` offers plain read-only access;
  - `relate clone --to-snapshot-format json` plus `relate info --json` make the auditor hand-over of a client file: a readable snapshot that Relate still opens, with counts, constraints, indexes and a sha256.

  The full inventory, including what we left out and why, is in `docs/relate-features.md`.
- **Law ingestion:** BWB XML parsing, pdftotext, and Tesseract (nld/eng, 300 dpi, word confidence) for scans. In the browser: pdf.js, DOMParser and a citation parser for Dutch and English references, including "tweede lid" style ordinals.
- **Tested twice:** an independent Python implementation computes the expected answer for every test client and office. The Cypher queries give the same answers today and on 10 July 2029.

## Challenges we ran into
- **Law changes, duties stay.** A duty is not an article. We made the article a dated edge of the duty, so the duty survives a new law and its history stays visible.
- **No article in the text.** Real procedures often describe what they do without citing a law. Full-text proposals plus a human confirmation keep the graph honest: nothing counts as covered by guesswork.
- **Getting the law right.** We checked the supervisor of every sector against Wwft art. 1d. We read the AMLR article numbers from the official text instead of trusting memory. And we found and fixed a wrong regulation number in our own sources.
- **Being honest about the rule set.** The law texts are official and verbatim. The layer that links duties to articles, documents to legal forms and supervisors to sectors was compiled for this project and checked against the law. Whatever is not yet verbatim law is marked `pending` or `summary` in the graph, so an office knows what to review.
- **Client data stays local.** The shared graph holds public law. Each client file pulls only the slice it needs.

## Accomplishments that we're proud of
- One query that connects the law, a company's own procedure and real fines, and shows both "today" and "after the AMLR".
- Every answer can be traced: from a duty to the verbatim article, from an AI claim to the nodes it read.
- It runs entirely in a browser tab, on Relate in WebAssembly, and every Relate feature it uses can be run live from the **Relate inside** panel.

## What we learned
An embedded graph per record changes how you think about compliance data. Isolation, retention and hand-over come for free, while the connected context (law, rules, history) can still be shared as small, public graph files.

## What's next
Read in the supervisors' guidance (DNB, AFM) and the Dutch implementing act once it is adopted. Add the remaining Wwft sectors. Test real (anonymised) procedures. And let the agent propose updates to a procedure for each `REPLACED_BY` edge.

## Built with
Relate (single-file stores, WebAssembly, CLI, MCP, schema DDL, full-text and vector indexes, quantified paths, PROFILE, clone/info) · Cypher · Tesseract (CLI and WebAssembly) · Python (standard library) · Tesseract · poppler · pdf.js · Cytoscape.js · Neo4j 5 (optional, central rules)

*All clients, offices and the example company are fictitious. Enforcement cases are published decisions of DNB and the Openbaar Ministerie, each linked to its source.*
