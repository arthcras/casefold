# Demo video (1:57) — `casefold-demo.mp4`

Recorded from the viewer with Playwright (`web/`, Relate 1.1.0 in WebAssembly), with captions in the picture and an English voice-over generated locally with the open Kokoro text-to-speech model (no text sent to a service). Each scene lasts as long as its narration.
- 0:16: **exploring the graph**: find a node, a relationship's properties, a node's neighbours, full screen.
- 0:33: **New client from documents**. The example structure chart and a scanned UBO register extract are read in the browser (the chart's vector paths, and OCR with Tesseract in WebAssembly). Nothing is pre-ticked: the officer selects the proposals and confirms them, and the review follows.
- 1:27: the **Relate inside** panel, which runs each Relate feature live in the page (see `docs/relate-features.md`).
- The end card gives the live prototype, https://arthcras.github.io/casefold/ .

| Time | Voice-over |
|---|---|
| 0:00 | This is Casefold: anti-money-laundering compliance as connected context, on Relate by Neo4j. Every answer is a Cypher query. |
| 0:09 | Each client is its own single-file Relate store, and Relate runs right here in the browser, compiled to WebAssembly. |
| 0:16 | Explore it like a graph: find a node, click a relationship for its properties, and expand a node's neighbours, full screen if you like. |
| 0:26 | Who is the beneficial owner? A Cypher query walks the ownership chain, ground by ground, each with its article. |
| 0:33 | Now a new client, from its own documents. The structure chart and the scanned register extract are read right here in the browser. Every fact points to its place in the chart, and nothing enters the file until the officer confirms it. |
| 0:47 | The review runs on that data: three beneficial owners, and Lina Brouwer is missing from the UBO register. No AI involved. |
| 0:56 | The sector register: supervisor, licence and duties, with the Dutch AML act and the EU regulation read in, article by article. |
| 1:05 | We test a fictitious payment institution: per duty, the article, the procedure section that cites it, and real fines. |
| 1:12 | No article cited? Relate's full-text index proposes a section, the vector index agrees, and one click confirms it. |
| 1:20 | In July twenty twenty-seven the EU regulation replaces the Dutch act, and the old procedure becomes a work list. |
| 1:27 | Relate inside runs every feature live. A quantified path pattern multiplies the shares across ownership hops. A shortest path gives the route. |
| 1:36 | Relate enforces the Neo4j 5 schema: the duplicate is refused. PROFILE shows the plan. |
| 1:43 | The same files run on the Relate command line, and over MCP for an AI agent that may only cite what it read. |
| 1:51 | Casefold, on Relate. Try it yourself at arthcras dot github dot io, slash casefold. |

The Devpost rules allow a video of up to 2 minutes.
