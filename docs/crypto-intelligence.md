# Casefold Crypto Intelligence

Casefold for crypto: who supervises crypto in each jurisdiction and under which law, every public enforcement case where it went
wrong (with the amount, the law broken and the decision), the sanctions lists, and later the wallet addresses on them. Same principles
as Casefold: every fact has its source, what is read from a source is a proposal until a person confirms it, every answer is a Cypher
query in Relate, and a score or a match is information for the customer's own decision, never a verdict.

## Order of work

1. **Wave 1, the Netherlands.** AFM (MiCA licence, conduct, AML), DNB (AML for banks and EMIs with crypto services; the registration
   regime before MiCA), FIU-Nederland, OM. Laws: MiCA, TFR, Wwft, Sanctiewet 1977, AMLR from 10 July 2027, DAC8. The ids are those of
   the Casefold sector register (`NL:afm`, `NL:dnb`, `NL:mica`, `NL:wwft`, ...), so the crypto register and the KYC register join.
2. **Wave 2, the EU.** ESMA (MiCA register of CASPs), EBA, AMLA; national supervisors of the largest markets.
3. **Wave 3, worldwide.** US, UK, Switzerland, Singapore, Hong Kong, Japan, South Korea, UAE, Australia, Canada, Brazil, South Africa,
   Curaçao, and the global standards (FATF R.15 and R.16, OECD CARF; CRS and FATCA as the non-crypto counterparts).

## What is in the repo

| Path | What |
|---|---|
| `data/crypto/jurisdictions.json` | 18 jurisdictions: crypto supervisors with their role and AML flag, regime, laws; `verify: true` where still to check against the supervisor's own site |
| `data/crypto/cases.json` | public enforcement cases, each with the authority, measure, amount as published, laws violated and the source URL; the collection queue |
| `data/crypto/sanctions_lists.json` | the lists to import daily (OFAC SDN with digital currency addresses, EU, UN, UK, NL) |
| `schema/crypto.cypher` | keys, required fields and indexes, including a full-text index on the cases |
| `casefold/build_crypto.py` | checks the data, builds `register/crypto.rl` with the Relate CLI and exports `web/data/crypto.json` |
| `queries/crypto/` | 01 register, 02 cases, 03 cases per law, 04 sanctions lists, 05 full-text search, 06 the same company in more than one country, 07 per article (duty, cases, fines, replaced by) (`python3 casefold/ask.py register/crypto.rl crypto/03`) |
| `tests/test_crypto.py` | data checks, then the register and every query (run by `run.sh` and in CI) |
| `web/crypto.html` | the public viewer, laid out like Casefold: views left, the graph in the middle with the answer below, the inspector right (click to inspect, double-click to expand). Supervision per country, Cases and fines, Sanctions and screening, Add a source, Search; plain words, no queries shown. Relate in WebAssembly (`web/vendor/relate`), the same statements as the build |

## The graph

```
(:Regulator)-[:SUPERVISES {role, aml}]->(:Sector)-[:IN_JURISDICTION]->(:Jurisdiction)
(:Sector)-[:SUBJECT_TO]->(:Law)
(:Source {kind:'case', date, amount, currency, url})-[:BY]->(:Regulator)
(:Source)-[:AGAINST]->(:Entity)   (:Source)-[:VIOLATED {art}]->(:Law)   (:Source)-[:IN_JURISDICTION]->(:Jurisdiction)
(:SanctionsList)-[:PUBLISHED_BY]->(:Regulator)        next: (:SanctionsList)-[:LISTS]->(:Entity|:Address)
(:Law)-[:HAS_ARTICLE]->(:Article {heading, duty, text, status})-[:REPLACED_BY]->(:Article)
(:Source)-[:VIOLATED_ARTICLE {lids}]->(:Article)   (:Source)-[:UNDER_POWER {art}]->(:Law)
(:Source)-[:CITES {art}]->(:Law)   (:Source)-[:NAMES]->(:Address)      from sources read in and confirmed
```

## Next steps

- [x] NL: the crypto enforcement measures of DNB, AFM and OM since 2020 from their own sites: Binance 2022, Coinbase 2023, Kraken 2023 (last onder dwangsom), an unnamed provider 2023 (reduced by the court), KuCoin 2024 (last onder dwangsom), Bybit 2024, OKX 2025, MEXC 2025 (AFM warning, MiCAR art. 59), Knaken 2026 (OM bankruptcy petition).
- [x] NL: the exact articles from the DNB decisions: six decisions (Binance, Coinbase, Kraken, the unnamed provider, Bybit, OKX) find art. 23b(1)(2) and 23c(3) Wwft violated, under art. 30 (fine) or art. 29 (last onder dwangsom). These articles have lapsed (`Vervallen` in the Wwft of 1 July 2026) and are `REPLACED_BY` MiCAR art. 59.
- [ ] NL: KuCoin 2024: the articles from the decision; the court rulings (ECLI) on these decisions; whether the unnamed provider is Foris DAX MT (Crypto.com), as date, amount and publication date suggest.
- [x] NL: MiCA (149 articles), TFR (40) and DAC8 (4, the amending articles) read in from EUR-Lex in Dutch and English: `laws/NL_mica_*`, `laws/NL_tfr_*`, `laws/EU_dac8_*`, by the `crypto-sources` workflow (EUR-Lex and DNB refuse the runner's direct requests; the Publications Office serves the PDF). The English files carry a few false article starts from cross-references (MiCA "290", TFR "59", "60"); the Dutch files are clean and are the ones used.
- [x] `data/crypto/articles.json`: 22 key articles (MiCAR 59-63, 67, 68, 70, 75, 76, 94, 111, 143; TFR 14, 16, 17, 19, 23; Wwft 23b, 23c, 29, 30) with their text from the law files; query 07 per article: duty, cases, fines, replaced by.
- [ ] Crypto duties with `valid_from` / `valid_to` in the Casefold duty map (`data/rules/duty_map.json`).
- [ ] NL: AFM warnings on unlicensed crypto providers as `Entity` with source.
- [x] Sanctions: OFAC SDN (19,571 entries, 1,081 crypto addresses), EU (6,269), UN (1,007) and UK (6,447) fetched by `casefold/fetch_sanctions.py` (`sanctions` workflow, daily once on `main`) into `data/crypto/sanctions/`; listed entities with crypto addresses in the graph (`SanctionsList`-`LISTS`->`Entity`-`CONTROLS`->`Address`); every name in `web/data/sanctions_names.json` for name screening; a case party whose name matches a listed entity gets `POSSIBLY_SAME` (a lead, e.g. Garantex).
- [ ] NL: the national terrorism sanctions list.
- [ ] Agent: extend `casefold/agent_mcp.py` with `regulation_for`, `cases_like`, `screen_address`; the grounding check stays.
- [ ] Wave 2 and 3, jurisdiction by jurisdiction, the same steps.
- [x] On chain: `casefold/fetch_chain.py` (`chain` workflow) traces the listed addresses of Garantex (OFAC, EU) and Grinex (OFAC) with public explorers (mempool.space, Blockscout, TronGrid): the latest transfers of each address and of its largest counterparties (two hops), `data/crypto/chain/`. In the graph: `(:Address)-[:SENT {asset, amount, count, first, last, tx}]->(:Address)`, only native coins and the known USDT and USDC contracts (lookalike tokens marked `*` and left out). Query 08 exposure per listed entity, 09 counterparties shared by two listed entities; the viewer's *Trace on chain* view and exposure in *Screen*.
- [x] Risk typology (`data/crypto/risk_categories.json`, query 10): one classification for what an address belongs to (sanctioned entity, terrorist financing, state-sponsored theft, cybercrime, drug trafficking, darknet, scam, stolen funds, mixer, high-risk exchange, ...) and what went wrong in a case (unlicensed service, AML failure, sanctions violation, money laundering, fraud), with a severity; listed entities get categories from their sanctions programmes, cases their typologies.
- [x] Exposure wheel in the viewer, as investigators know it: the outer ring direct exposure per category, the inner ring indirect exposure one hop further for unattributed counterparties; in Trace on chain and in Screen.
- [ ] On chain next: more listed entities, deeper hops on demand, clustering (common inputs on bitcoin), labels for exchanges, and NeoArbiTrader's block harvester for full history instead of the latest transfers.

Sources for third-party lists and labels (OpenSanctions, Chainabuse, commercial labels) are used only under a licence that allows
commercial use; the licence is recorded per source.
