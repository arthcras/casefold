#!/usr/bin/env bash
# Build the demo case and the test clients, ask the main questions, and prepare the browser viewer.
# Netherlands only: one test office per sector under supervision now (28) or coming under it with the AMLR (9), two test clients each; the UBO question is always
# asked from the office that serves the client, under the rule of its supervisor (Uitvoeringsbesluit Wwft 2018 art. 3).
set -euo pipefail
cd "$(dirname "$0")"
bash laws/ingest.sh | grep -v '^(skipping' || true                       # the law texts in laws/sources/ -> one Relate file per law, version and language
python3 casefold/build_duties.py | tail -1                           # dynamic duties: the article per legal regime (Wwft until 9 July 2027, then AMLR/Iwt), from the laws read in under laws/
python3 casefold/make_test_cases.py                                    # 14 test offices: the Wwft sectors under DNB or the AFM, 28 test clients + expected answers
python3 casefold/build_case.py data/cases/*.json
python3 casefold/run_tests.py                                          # every office: who is the UBO, ground by ground, and the sector duties
# the same offices on a later date: the AMLR sectors are obliged from 10 July 2027 (football 2029), the EUR 15,000 threshold becomes EUR 10,000
CASEFOLD_ON=2029-07-10 python3 casefold/make_test_cases.py && python3 casefold/run_tests.py | tail -1
python3 casefold/make_test_cases.py && python3 casefold/build_case.py data/testcases/*.json --out tests/cases > /dev/null && python3 casefold/build_office.py --tests > /dev/null   # back to today
echo; python3 casefold/ask.py cases/nl-kalmora.rl 13                   # which rule applies: office, supervisor, article
echo; python3 casefold/ask.py cases/nl-kalmora.rl 14                   # every entity: legal form, how it is tested, grounds
echo; python3 casefold/ask.py cases/nl-kalmora.rl 03                   # the beneficial owners, compared with the declaration
echo; python3 casefold/ask.py cases/nl-kalmora.rl 16                   # besides the UBO: the other duties of the sector, and what they mean here
echo; python3 casefold/ask.py cases/nl-kalmora.rl 01
echo; python3 casefold/ask.py cases/nl-kalmora.rl 05
echo; python3 casefold/ask.py tests/cases/nl-investment-institutions-2.rl 03   # a C.V.: votes decide for the managing partner
echo; python3 casefold/ask.py tests/cases/nl-electronic-money-institu-1.rl 15    # five shareholders of 20%: nobody qualifies, fallback
echo; python3 casefold/ask.py tests/cases/nl-currency-exchange-instit-1.rl 16   # exchange office: occasional transactions, FIU reporting, sanctions
echo; python3 casefold/ask.py tests/cases/nl-banks-1.rl 17                     # monitoring: the client's transactions with its 3 sub-clients against its service profile
# the sector register: one file with the classification of every sector (FATF scope, category), its supervisor, its duties and the office files
python3 casefold/build_register.py
echo; python3 casefold/ask.py register/sectors.rl register/01       # the sector map: category, FATF scope, supervisor, obliged since or from
echo; python3 casefold/ask.py register/sectors.rl register/02       # which duties are shared and which belong to one corner of the market
echo; python3 casefold/ask.py register/sectors.rl register/03       # per authority: AML supervisor, licensing authority, FIU-Nederland, AP
echo; python3 casefold/ask.py register/sectors.rl register/04       # the legislation: Wwft, Sanctiewet 1977, Rtsw, Wft, Wtt 2018, Wok, AVG, AMLR, ...
echo; python3 casefold/ask.py register/sectors.rl register/05       # licence or not: who grants it, one body or two
echo; python3 casefold/ask.py register/sectors.rl register/06       # business typologies: SBI code, risk factors, risk band
# two levels, two kinds of Relate file: one file per client, and one file per office (the office itself + an overview of its client files, no client names)
python3 casefold/build_office.py                                       # offices/INST-NL.rl from cases/
echo; python3 casefold/ask.py offices/INST-NL.rl office/01             # the office itself: its periodic duties and the evidence on file
echo; python3 casefold/ask.py tests/offices/OFF-banks.rl office/02     # a test office: its client files and the signals each gives
echo; python3 casefold/ask.py tests/offices/OFF-banks.rl office/03     # which signals recur across its clients
echo; python3 casefold/ask.py tests/offices/OFF-banks.rl office/04     # KYCC across clients: a counterparty in more than one client file (by key, no name)
echo; python3 casefold/ask.py tests/cases/nl-trust-offices-wtt-2018-1.rl 16      # trust office: Wwft and Wtt 2018 (purpose of the services, acceptance memorandum)
echo; python3 casefold/ask.py tests/cases/nl-crypto-asset-service-pro-1.rl 16   # crypto-asset service provider: AFM, MiCA licence, TFR
if command -v tesseract >/dev/null && command -v pdftoppm >/dev/null; then
  python3 casefold/ingest.py cases/nl-kalmora.rl data/documents/nl-kalmora/*
  echo; python3 casefold/ask.py cases/nl-kalmora.rl 09 term=middellijk
  if python3 -c 'import pdfplumber' 2>/dev/null; then                 # own data: the same client from the documents it delivered
    echo; python3 casefold/new_client.py examples/kalmora-from-documents          # build, read (OCR), structure chart -> proposals, review
    python3 casefold/structure_chart.py cases/nl-kalmora-docs.rl --confirm all > /dev/null   # the compliance officer confirms
    echo; python3 casefold/new_client.py examples/kalmora-from-documents --review | sed -n '/Beneficial owners/,$p'
    python3 tests/test_structure_chart.py                                         # same structure and UBOs as the hand-built file
    python3 casefold/new_client.py examples/kalmora-from-documents --template nl-kalmora-new   # the starting point of 'New client from documents' in the viewer
  else
    echo; echo "(skipping the structure chart: pip install pdfplumber)"
  fi
else
  echo; echo "(skipping OCR: install tesseract and poppler to read the scanned documents)"
fi
if python3 -c 'import sentence_transformers' 2>/dev/null; then
  python3 casefold/embed.py cases/*.rl
  echo; python3 casefold/semantic.py cases/nl-kalmora.rl "Wie is UBO als niemand meer dan 25% heeft?" --scope law
else
  echo; echo "(skipping embeddings: pip install sentence-transformers to enable questions in your own words)"
fi
# reasoning with memory: learn from one case, approve the lesson, recognise it in a test client of another office
rm -rf memory/longterm.rl
echo; python3 casefold/reason.py cases/nl-kalmora.rl
python3 casefold/memory.py approve cases/nl-kalmora.rl P-high-risk-counterparty-kycc-open
echo; python3 casefold/reason.py tests/cases/nl-banks-1.rl                  # a bank's client: monitoring finds structuring below EUR 10,000
python3 casefold/memory.py approve tests/cases/nl-banks-1.rl P-structuring-below-cash-limit
echo; python3 casefold/reason.py tests/cases/nl-currency-exchange-instit-1.rl   # an exchange office (other office, other supervisor role): "seen before"
echo; python3 casefold/memory.py list
echo; python3 casefold/ask.py cases/nl-kalmora.rl 10
# AI memory: a replayed agent session over MCP; every claim must rest on nodes the agent actually read
echo; python3 casefold/agent_demo.py cases/nl-kalmora.rl
echo; python3 casefold/ask.py cases/nl-kalmora.rl 12
# the schema of each kind of file (schema/*.cypher): keys, required fields, types and indexes; Relate checks them against the data
python3 casefold/apply_schema.py register/sectors.rl offices/*.rl cases/*.rl tests/offices/*.rl tests/cases/*.rl $(ls laws/*.rl 2>/dev/null)
python3 casefold/export_view.py register/sectors.rl cases/nl-kalmora.rl $(ls cases/nl-kalmora-docs.rl cases/nl-kalmora-new.rl 2>/dev/null) offices/*.rl tests/cases/*.rl tests/offices/*.rl $(ls laws/*.rl 2>/dev/null)
python3 casefold/export_examples.py                                       # example documents for 'New client from documents'
python3 casefold/handover.py cases/nl-kalmora.rl                     # auditor hand-over: relate clone (JSON snapshot) + relate info + sha256
echo; echo "Viewer: cd web && python3 -m http.server 8000   then open http://localhost:8000"
