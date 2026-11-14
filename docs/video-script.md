# Demo video (1:58) — `casefold-demo.mp4`

Recorded from the viewer with Playwright (`web/`, Relate in WebAssembly), with captions in the picture and an English voice-over generated locally with the open Kokoro text-to-speech model (no text sent to a service). Each scene lasts as long as its narration.
- 0:24: **New client from documents**. The example structure chart and a scanned UBO register extract are read in the browser (the chart's vector paths, and OCR with Tesseract in WebAssembly). The officer confirms the proposals, and the review follows.
- 1:23: the **Relate inside** panel, which runs each Relate feature live in the page (see `docs/relate-features.md`).

| Time | Voice-over |
|---|---|
| 0:00 | This is Casefold: anti-money-laundering compliance as connected context, on Relate by Neo4j. Every answer is a Cypher query. |
| 0:09 | Each client is its own single-file Relate store, and Relate runs right here in the browser, compiled to WebAssembly. |
| 0:17 | Who is the beneficial owner? A Cypher query walks the ownership chain, ground by ground, each with its article. |
| 0:24 | Now a new client, from its own documents. The structure chart is read box by box and line by line, and the scan with OCR, right here in the browser. Every fact points to its place in the chart, and the compliance officer confirms it. |
| 0:38 | The review runs on that data: three beneficial owners, and Lina Brouwer is missing from the UBO register. No AI involved. |
| 0:47 | The sector register: supervisor, licence and duties. The Dutch AML act and the EU regulation are read in, article by article. |
| 0:56 | We test a fictitious payment institution. Per duty: the article, the procedure section that cites it, and real fines where the same duty went wrong. |
| 1:05 | No article cited? Relate's full-text index proposes a section, the vector index agrees, and one click confirms it. |
| 1:13 | In July twenty twenty-seven the EU regulation replaces the Dutch act. Each duty moves to its new article, and the old procedure becomes a work list. |
| 1:23 | Relate inside runs every feature live. A quantified path pattern multiplies the shares across ownership hops. A shortest path gives the route. |
| 1:33 | Relate enforces the Neo4j 5 schema. Try to break it: the duplicate is refused. |
| 1:39 | Vector search with a graph match, embeddings computed in the page. And PROFILE shows the query plan. |
| 1:45 | The same files run on the Relate command line, and over MCP for an AI agent that may only cite what it read. |
| 1:53 | Casefold. Your own documents and the law, connected, on Relate. |
