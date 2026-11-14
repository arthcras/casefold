#!/usr/bin/env python3
"""Check the structure-chart route against the hand-built demo client.

The fictitious Kalmora group exists twice: data/cases/nl-kalmora.json (the structure typed in by hand) and
examples/kalmora-from-documents/documents/structure_chart.pdf (the chart a client would deliver). This test reads the chart
and checks that it yields the same ownership, control and board relations, and, after confirmation, the same beneficial
owners on the same grounds as the hand-built file.

usage:  python3 tests/test_structure_chart.py      # needs pdfplumber; run after casefold/new_client.py and --confirm all
"""
import json, os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, 'casefold'))
from build_case import find_relate
from structure_chart import read_chart, relation_of, relate_q

case = json.load(open(os.path.join(HERE, 'data', 'cases', 'nl-kalmora.json'), encoding='utf-8'))
names = {e['id']: e['name'] for e in case['entities']} | {'client': case['client']['name']}
want = {(names[r['from']], names[r['to']], r['type'], r.get('pct') if r['type'] == 'OWNS' else None,
         r.get('votes', r.get('pct')) if r['type'] in ('OWNS', 'BOARD_OF') else None)
        for r in case['relations'] if r['type'] in ('OWNS', 'CONTROLS', 'BOARD_OF')}
boxes, rels, _ = read_chart(os.path.join(HERE, 'examples', 'kalmora-from-documents', 'documents', 'structure_chart.pdf'))
got = set()
for r in rels:
    x = relation_of(r['label'], r['dashed'])
    got.add((r['src']['name'], r['dst']['name'], x['type'], x.get('pct') if x['type'] == 'OWNS' else None, x.get('votes') if x['type'] in ('OWNS', 'BOARD_OF') else None))
fails = [f'missing from the chart reading: {w}' for w in sorted(want - got, key=str)] + [f'not in the hand-built file: {g}' for g in sorted(got - want, key=str)]

relate = find_relate(None)
q = open(os.path.join(HERE, 'queries', '03_beneficial_owners.cypher'), encoding='utf-8').read()
q = '\n'.join(l for l in q.splitlines() if not l.startswith('//'))
on = {'on': '2026-11-13'}
key = lambda rows: sorted((u['person'], u['ubo'], tuple(sorted(u['grounds_met'])), u['ownership'], u['votes']) for u in rows)
docs_db = os.path.join(HERE, 'cases', 'nl-kalmora-docs.rl')
if os.path.exists(docs_db):
    a, b = key(relate_q(relate, os.path.join(HERE, 'cases', 'nl-kalmora.rl'), q, on)), key(relate_q(relate, docs_db, q, on))
    if a != b:
        fails.append(f'beneficial owners differ:\n  hand-built {a}\n  from chart {b}')
print(f'structure chart: {len(boxes)} boxes, {len(rels)} relations read; {len(want)} expected; '
      + ('beneficial owners identical to the hand-built file; ' if os.path.exists(docs_db) and not any('differ' in f for f in fails) else '')
      + ('OK' if not fails else f'{len(fails)} FAILED'))
for f in fails:
    print('  ' + f)
sys.exit(1 if fails else 0)
