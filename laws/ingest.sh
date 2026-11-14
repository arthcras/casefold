#!/usr/bin/env bash
# Read the law texts in laws/sources/ into one Relate file per law, version and language (casefold/law_ingest.py).
# Missing sources are skipped: download them with casefold/law_fetch.py, or save them by hand under these names.
set -euo pipefail
cd "$(dirname "$0")/.."
ing() { [ -f "$1" ] && python3 casefold/law_ingest.py "$@" || echo "(skipping $1: not in laws/sources/)"; }
ing laws/sources/wwft-2026-07-01-nl.xml   --law NL:wwft  --version 2026-07-01 --lang nl
ing laws/sources/rtsw-nl.xml              --law NL:rtsw  --version 2009-07-01 --lang nl
ing laws/sources/sanctiewet-1977-nl.pdf   --law NL:sw1977 --version 2025-03-01 --lang nl --title "Sanctiewet 1977" --url https://wetten.overheid.nl/BWBR0003296
ing laws/sources/amlr-nl.pdf              --law EU:amlr  --version 2027-07-10 --lang nl --title "Verordening (EU) 2024/1624 (AMLR)" --url https://eur-lex.europa.eu/eli/reg/2024/1624/oj
ing laws/sources/amlr-en.pdf              --law EU:amlr  --version 2027-07-10 --lang en --title "Regulation (EU) 2024/1624 (AMLR)" --url https://eur-lex.europa.eu/eli/reg/2024/1624/oj
