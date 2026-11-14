# Demo video (1:59) — `casefold-demo.mp4`

Recorded from the viewer with Playwright (`web/`, Relate in WebAssembly), with captions in the picture and an English voice-over generated locally with the open Kokoro text-to-speech model (no text sent to a service). Each scene lasts as long as its narration.
- 0:17: **exploring the graph**: zoom, find a node, a relationship's properties, expand a node's neighbours, full screen, and a node on a page of its own.
- 0:34: **New client from documents**. The example structure chart and a scanned UBO register extract are read in the browser (the chart's vector paths, and OCR with Tesseract in WebAssembly). The officer confirms the proposals, and the review follows.
- 1:28: the **Relate inside** panel, which runs each Relate feature live in the page (see `docs/relate-features.md`).
- The end card gives the live prototype, https://arthcras.github.io/casefold/ .

| Time | Voice-over |
|---|---|
| 0:00 | This is Casefold: anti-money-laundering compliance as connected context, on Relate by Neo4j. Every answer is a Cypher query. |
| 0:09 | Each client is its own single-file Relate store, and Relate runs right here in the browser, compiled to WebAssembly. |
| 0:16 | Explore it like a graph. Zoom in, find a node, click a relationship for its properties, expand a node's neighbours, and open any node on a page of its own. |
| 0:27 | Who is the beneficial owner? A Cypher query walks the ownership chain, ground by ground, each with its article. |
| 0:34 | Now a new client, from its own documents. The structure chart is read box by box and line by line, and the scan with OCR, right here in the browser. Every fact points to its place in the chart, and the compliance officer confirms it. |
| 0:48 | The review runs on that data: three beneficial owners, and Lina Brouwer is missing from the UBO register. No AI involved. |
| 0:56 | The sector register: supervisor, licence and duties, with the Dutch AML act and the EU regulation read in, article by article. |
| 1:05 | We test a fictitious payment institution: per duty, the article, the procedure section that cites it, and real fines. |
| 1:13 | No article cited? Relate's full-text index proposes a section, the vector index agrees, and one click confirms it. |
| 1:21 | In July twenty twenty-seven the EU regulation replaces the Dutch act, and the old procedure becomes a work list. |
| 1:28 | Relate inside runs every feature live. A quantified path pattern multiplies the shares across ownership hops. A shortest path gives the route. |
| 1:37 | Relate enforces the Neo4j 5 schema: the duplicate is refused. PROFILE shows the plan. |
| 1:44 | The same files run on the Relate command line, and over MCP for an AI agent that may only cite what it read. |
| 1:52 | Casefold, on Relate. Try it yourself at arthcras dot github dot io, slash casefold. |
