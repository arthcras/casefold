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
| `queries/crypto/` | 01 register, 02 cases, 03 cases per law, 04 sanctions lists, 05 full-text search (`python3 casefold/ask.py register/crypto.rl crypto/03`) |
| `tests/test_crypto.py` | data checks, then the register and every query (run by `run.sh` and in CI) |
| `web/crypto.html` | the viewer: Register, Cases and fines, Add a source (proposals, confirm), Screen, Ask the graph; Relate in WebAssembly, the same statements as the build |

## The graph

```
(:Regulator)-[:SUPERVISES {role, aml}]->(:Sector)-[:IN_JURISDICTION]->(:Jurisdiction)
(:Sector)-[:SUBJECT_TO]->(:Law)
(:Source {kind:'case', date, amount, currency, url})-[:BY]->(:Regulator)
(:Source)-[:AGAINST]->(:Entity)   (:Source)-[:VIOLATED {art}]->(:Law)   (:Source)-[:IN_JURISDICTION]->(:Jurisdiction)
(:SanctionsList)-[:PUBLISHED_BY]->(:Regulator)        next: (:SanctionsList)-[:LISTS]->(:Entity|:Address)
(:Source)-[:CITES {art}]->(:Law)   (:Source)-[:NAMES]->(:Address)      from sources read in and confirmed
```

## Next steps

- [ ] NL: every crypto decision of DNB and AFM since 2020, read in from the decision itself (replace the `verify` record for Binance 2022).
- [ ] NL: MiCA, TFR and DAC8 read in article by article with `law_fetch.py` / `law_ingest.py`; crypto duties with `valid_from` / `valid_to`.
- [ ] NL: AFM warnings on unlicensed crypto providers as `Entity` with source.
- [ ] Sanctions: daily import of OFAC SDN (incl. digital currency addresses), EU, UN, UK into `SanctionsList`-`LISTS`->`Entity|Address`.
- [ ] Agent: extend `casefold/agent_mcp.py` with `regulation_for`, `cases_like`, `screen_address`; the grounding check stays.
- [ ] Wave 2 and 3, jurisdiction by jurisdiction, the same steps.
- [ ] Blockchain layer (from NeoArbiTrader's block harvester): the neighbourhood of known addresses, exposure with explanation.

Sources for third-party lists and labels (OpenSanctions, Chainabuse, commercial labels) are used only under a licence that allows
commercial use; the licence is recorded per source.
