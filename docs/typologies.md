# Transaction typologies, instruments and supervisory guidance

Casefold labels crypto transfers with **transaction typologies**: fixed rules over the traced transfers
(`casefold/typologies.py`, thresholds in `data/crypto/tx_typologies.json`). A label is a lead for review, never proof.

## In the graph (Relate in the browser, the same Cypher on Neo4j)

| Node / relationship | Meaning |
|---|---|
| `(:TxTypology {id, name, severity, level, rule})` | one per typology, e.g. `TT-PASS` |
| `(:Address)-[:SHOWS {asset, evidence, n, first, last}]->(:TxTypology)` | a wallet shows the pattern |
| `SENT.typologies` | the typologies on a transfer (list of ids) |
| `(:Guidance)`, `(:Regulator)-[:ISSUED]->(:Guidance)` | FATF, EBA and DNB documents (`data/crypto/guidance.json`) |
| `(:TxTypology)-[:FLAGGED_IN {section, page, says}]->(:Guidance)` | where the guidance names the pattern |
| `(:Instrument)`, `(:Instrument)-[:ADDRESSED_IN]->(:Guidance)` | chain, transaction model, standard, issuer, freeze power (`data/crypto/instruments.json`) |

Example: wallets that pass money through and also reach a listed party

```cypher
MATCH (a:Address)-[:SHOWS]->(:TxTypology {id: 'TT-PASS'})
MATCH (a)-[s:SENT]->(b:Address) WHERE 'TT-LISTED' IN s.typologies
RETURN a.key, b.key, s.asset, s.amount
```

## Typologies

TT-LISTED, TT-SANCTIONED-ASSET, TT-HIGHRISK, TT-SERVICE (from lists and labels); TT-FANOUT, TT-FANIN, TT-PASS,
TT-STRUCT, TT-PEEL (Bitcoin only), TT-SWAP, TT-ROUND, TT-LARGE, TT-LOOKALIKE (address poisoning). The rules and their
thresholds are in `tx_typologies.json`; the back office (Data → Transaction typologies) changes them with four eyes,
and they take effect at the next build.

## Guidance

Summaries are Casefold's paraphrase with section and page. `verify: true` marks an item that must be checked against
its source before it is used as a norm (the DNB 2019 indicators may have been withdrawn). Only verified items enter
the norm register of the findings.
