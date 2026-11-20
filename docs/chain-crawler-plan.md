# Plan: Casefold chain crawler (trace any wallet, on demand)

Status: plan, 2026-11-20. Nothing runs on a server until Arthur approves the server step.

## Goal

Trace any wallet when it is read in, not only the wallets around listed parties that the nightly
pipeline (`casefold/fetch_chain.py`, workflow `chain.yml`) traces today. Same graph model as now
(`(:Address)-[:SENT]->(:Address)`, typologies, labels), so the app, findings and reports stay the same.

## Scope: chains in three priorities

| Priority | Chains | Model | Source (start) | Source (production) |
|---|---|---|---|---|
| 1 | Tron | account + TRC-20 | TronGrid (key) | TronGrid paid or an RPC provider |
| 1 | Ethereum | account + ERC-20 | Blockscout (no key, as now) | Etherscan multichain key |
| 1 | Bitcoin | UTXO | mempool.space | own Bitcoin node + address index (electrs / Fulcrum) |
| 2 | BNB Smart Chain, Polygon, Arbitrum, Base, Optimism, Avalanche | EVM, as Ethereum | Blockscout instances / Etherscan free | same Etherscan key (one key, many chains) |
| 2 | Solana | account + SPL tokens | Solana RPC provider (free tier) | paid RPC provider |
| 3 | TON, XRP Ledger, Litecoin | own models | public APIs | per chain |
| 3 | Monero | privacy coin | recognise only | recognise only |

One adapter per model, not per chain: all EVM chains share one adapter with the chain as a setting.

## Architecture

```
app (crypto.html)  --"trace this wallet now"-->  crawler API (FastAPI, on the Hetzner server)
                                                  |  queue (per chain, rate-limited)
                                                  |  adapters: evm | tron | utxo | solana | ...
                                                  v
                                   cache of fetched addresses (Postgres/SQLite: address, chain, fetched_at)
                                                  v
                                   Neo4j: Address, SENT (+ tx refs), typologies, labels  <-- same Cypher as Relate
```

- **Focused crawl.** Start at the wallet asked for; fetch its transfers; follow the widest flows up to N hops
  (default 3, top 5 per wallet, as in the app). Every fetched address is cached with its time, so a later trace
  reuses it and only asks for what is new.
- **Seeds grow the index.** Sanctions lists, cases and every wallet a client reads in become seeds; the index
  grows where investigations happen.
- **Evidence.** Every transfer keeps chain, tx hash, time, block and the API it came from, as now.
- **Typologies.** `casefold/typologies.py` runs on the new transfers after each crawl.
- **Cross-chain.** Bridges and swaps: first by recognising bridge and DEX contracts (labels), later by matching
  the deposit on one chain to the release on the other.
- **Credits.** A trace costs credits like a screening; the API counts calls per trace so the price can follow cost.

## Phases

| Phase | What | Done when |
|---|---|---|
| 1 | Crawler service with adapters for Tron, Ethereum, Bitcoin; cache; Neo4j writer; tests on recorded API answers | a wallet not yet in the data is traced 3 hops on the server |
| 2 | App: "Trace this wallet now" button, progress, result into the investigation; typologies on new data | a client wallet in an investigation gets its money flow within minutes |
| 3 | EVM chains (BNB, Polygon, Arbitrum, Base, Optimism, Avalanche) via the same adapter; bridge contracts labelled | flows across a bridge visible as a step |
| 4 | Solana adapter | Solana wallet traced |
| 5 | TON, XRP, Litecoin; Bitcoin on an own node when volume justifies it | per chain |

## What Arthur arranges (not in chat, not in git)

- Approval for the server step on Hetzner (the crawler runs next to Neo4j).
- API keys as server secrets: TronGrid/Tronscan (open), Etherscan (when we leave the free tiers), a Solana RPC key (phase 4).
- Billing of paid plans, if and when chosen.

## Costs (estimate, see the conversation of 2026-11-20)

- Build: no external costs.
- Prototype and pilot: free tiers, about EUR 0 a month.
- Production: about EUR 60-250 a month for data APIs; an own Bitcoin node later on an existing or extra server.

## Coverage compared

Chainalysis Reactor states 27+ blockchains, 40M+ assets, 325M+ swaps and 300+ bridges and DEXs
(chainalysis.com/product/reactor). After phase 4 Casefold covers about 12 chains; the EVM adapter makes more
EVM chains a setting. The hard part is not the number of chains but decoding swaps and bridges and the
attribution of addresses to parties; Casefold builds attribution from sanctions lists, enforcement cases and
analyst labels with four eyes.
