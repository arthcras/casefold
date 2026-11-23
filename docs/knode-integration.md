# Casefold ↔ KnodeCompliance

Same exchange as in `knode-platform/docs/casefold.md`, seen from Casefold. No connection between the two: files only.

- **In**: My investigations, *Upload a file* with a `casefold-handoff/1` from the Crypto tab of a Knode file. Casefold reads
  the wallets and transactions in its `text` (checked against the chain), adds the parties of the file, and remembers
  the file as `source` (dossier id and name) of the investigation.
- **Back**: *Send to Knode* saves `casefold-report/1`: `{format, sealed, sha256}`. `sealed` is exactly the JSON the
  evidence report seals; `investigation.source` names the Knode file, so Knode refuses it for another file.
- **Names**: *Names to Knode screening* saves a CSV (`id,name,type,aliases,country`) that the Knode screening-app reads.
  Its `screening.json` can be uploaded here again: level, themes and hits (sanctions, PEP, UBO) go onto the item with
  the same id and into the sealed report as a fact with its source.
