#!/usr/bin/env python3
"""Edge cases of the UBO question (queries/03_beneficial_owners.cypher) that the generated test clients do not reach.

One small fictitious structure, built as a real Relate file and asked with the same query as the viewer:

  client B.V.   <- 62.6%  Grensholding B.V.  <- 40% Bram Berg, 60% Jan van der Berg
                <- 25%    Anna Grens
                <- 12.4%  Widely Held Fund

  Bram Berg         40% x 62.6% = 25.04%  -> more than 25%: UBO (was missed when the share was rounded to 25.0 first)
  Anna Grens        exactly 25%           -> not more than 25%: not a UBO
  Jan van der Berg  controls the holding  -> UBO; the declaration names 'B. Berg' and 'Pieter van Dijk', so Jan is
                                             NOT declared (was 'declared' when one word of the name, 'van', was matched)
  Bram Berg         named as 'B. Berg'    -> declared (initial and surname)

usage:  python3 tests/test_ubo_boundaries.py      # needs relate on PATH (or RELATE_BIN)
"""
import copy, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, 'casefold'))
from build_case import find_relate, run

base = json.load(open(os.path.join(HERE, 'data', 'cases', 'nl-kalmora.json'), encoding='utf-8'))
case = copy.deepcopy(base)
case.update({'id': 'test-ubo-boundaries', 'questions': [], 'signals': [], 'counterparties': []})
case['client'] = {**base['client'], 'name': 'Grenstest B.V.'}
case['entities'] = [
    {'id': 'P_BRAM', 'kind': 'Person', 'name': 'Bram Berg', 'country': 'NL'},
    {'id': 'P_JAN', 'kind': 'Person', 'name': 'Jan van der Berg', 'country': 'NL'},
    {'id': 'P_ANNA', 'kind': 'Person', 'name': 'Anna Grens', 'country': 'NL'},
    {'id': 'C_HOLD', 'kind': 'Company', 'name': 'Grensholding B.V.', 'country': 'NL', 'legal_form': 'NL:lf:bv'},
    {'id': 'C_FUND', 'kind': 'Company', 'name': 'Widely Held Fund', 'country': 'NL'}]
own = lambda a, b, pct: {'from': a, 'to': b, 'type': 'OWNS', 'pct': pct, 'source': 'D1', 'where': 'register'}
case['relations'] = [own('C_HOLD', 'client', 62.6), own('P_ANNA', 'client', 25), own('C_FUND', 'client', 12.4),
                     own('P_BRAM', 'C_HOLD', 40), own('P_JAN', 'C_HOLD', 60)]
case['documents'] = [
    {'id': 'D1', 'title': 'Register extract (test)', 'doctype': 'register_extract', 'date': '2026-11-01', 'text': 'Grenstest B.V.'},
    {'id': 'D6', 'title': 'UBO declaration (test)', 'doctype': 'ubo_declaration', 'date': '2026-11-01',
     'text': "Verklaarde UBO's: B. Berg (via Grensholding)\nen Pieter van Dijk."}]

want = {  # person -> (ubo, declaration)
    'Bram Berg': (True, 'declared'),
    'Jan van der Berg': (True, 'not declared'),
    'Anna Grens': (False, 'not declared'),
}

relate = find_relate(os.environ.get('RELATE_BIN'))
with tempfile.TemporaryDirectory() as tmp:
    src = os.path.join(tmp, case['id'] + '.json')
    json.dump(case, open(src, 'w', encoding='utf-8'), ensure_ascii=False)
    subprocess.run([sys.executable, os.path.join(HERE, 'casefold', 'build_case.py'), src, '--out', tmp], check=True, capture_output=True, text=True)
    q = open(os.path.join(HERE, 'queries', '03_beneficial_owners.cypher'), encoding='utf-8').read()
    rows = run(relate, os.path.join(tmp, case['id'] + '.rl'), {'on': '2026-11-13'}, command=q, read=True)

got = {r['person']: (r['ubo'], r['declaration']) for r in rows}
share = {r['person']: r['ownership'] for r in rows}
fails = [f"{p}: expected ubo={w[0]}, declaration={w[1]!r}; got {got.get(p)}" for p, w in want.items() if got.get(p) != w]
if share.get('Bram Berg') != 25.0:
    fails.append(f"Bram Berg: the share is shown rounded to one decimal (25.0), got {share.get('Bram Berg')}")
print(f"UBO edge cases: {len(want) - len([f for f in fails if 'expected' in f])}/{len(want)} as expected"
      " (25.04% is a UBO, exactly 25% is not, 'van' does not make someone declared)")
if fails:
    print('\n'.join('   ' + f for f in fails))
    sys.exit(1)
