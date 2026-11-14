#!/usr/bin/env python3
"""Build the test clients (data/testcases/) and check that the UBO question, asked from each test office, gives the expected
answer (tests/expected.json): the beneficial owners ground by ground (question 03) or, when nobody qualifies, the senior managing
officials (question 15), and the other duties of the office's sector (question 16): which apply today, and whether the client's
transactions trigger a CDD threshold, an FIU indicator or the cash ban. A natural-person client has no UBO test.

usage:  python3 casefold/run_tests.py                 # all 56 test clients of the 28 test offices
        python3 casefold/run_tests.py banks lawyers   # only offices whose sector starts with these words
"""
import contextlib, glob, io, json, os, sys
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_case import find_relate, build, run, HERE

rel = find_relate(os.environ.get('RELATE_BIN'))
EXP = json.load(open(os.path.join(HERE, 'tests', 'expected.json'), encoding='utf-8'))
ON = next(iter(EXP.values()))['on']     # the date the expected answers were computed for (make_test_cases.py, CASEFOLD_ON)
q = lambda n: open(glob.glob(os.path.join(HERE, 'queries', n + '_*.cypher'))[0], encoding='utf-8').read().strip().rstrip(';').replace('$on', "'" + ON + "'")
Q03, Q15, Q16, Q17 = q('03'), q('15'), q('16'), q('17')
QO1 = open(glob.glob(os.path.join(HERE, 'queries', 'office', '01_*.cypher'))[0], encoding='utf-8').read().strip().rstrip(';').replace('$on', "'" + ON + "'")
only = [a.lower() for a in sys.argv[1:]]
out = os.path.join(HERE, 'tests', 'cases')
ok = bad = 0
by_sup, by_cat = {}, {}
for f in sorted(glob.glob(os.path.join(HERE, 'data', 'testcases', '*.json'))):
    cid = os.path.basename(f)[:-5]
    if only and not any(cid[3:].startswith(o) for o in only):
        continue
    with contextlib.redirect_stdout(io.StringIO()):
        db = build(f, rel, out, os.path.join(HERE, 'data', 'rulebook'))
    rows = run(rel, db, {}, command=Q03, read=True)
    got = {r['person']: sorted(g.split(': ')[1].split(' ')[0] for g in r['grounds_met']) for r in rows if r['ubo']}
    e_pre = EXP[cid]
    natural = json.load(open(f, encoding='utf-8'))['client'].get('person')
    fb = [] if got or natural or e_pre.get('no_cdd') else sorted(r['senior_managing_official'] for r in run(rel, db, {}, command=Q15, read=True))
    e = EXP[cid]
    duty = {r['duty_id']: r['status'] for r in run(rel, db, {}, command=Q16, read=True)}
    duty_ok = set(duty) == set(e['duties']) and all(duty[k].startswith(v) for k, v in e['duties'].items())
    mon_rows = run(rel, db, {}, command=Q17, read=True)
    mon = set()
    for r in mon_rows:
        if r['status'].startswith('FLAG'):
            if r['check'] in ('high_risk_country', 'sanctions_hit', 'kycc_open', 'indirect_high_risk'):
                mon |= {r['check'] + ':' + n.split(' (')[0] for n in r['status'][6:].split('; ')}
            else:
                mon.add(r['check'])
    mon_ok = mon == set(e['monitoring'])
    office, office_ok = {}, True        # the office's own evidence is checked in the office file, below
    duty_ok = duty_ok and mon_ok
    passed = got == e['ubo'] and fb == e['fallback'] and duty_ok
    ok += passed; bad += not passed
    by_sup.setdefault(e['supervisor'], [0, 0])[0 if passed else 1] += 1
    by_cat.setdefault(e.get('category') or '?', [0, 0])[0 if passed else 1] += 1
    short = lambda d: '; '.join(f"{k.split(' ', 1)[1]} [{', '.join(v)}]" for k, v in sorted(d.items())) or '-'
    flags = [v for v in duty.values() if v.split(':')[0] in ('VIOLATION', 'REPORT to FIU-NL', 'CDD required', 'in scope', 'FREEZE', 'EDD required', 'ASK for the customs declaration') or v.startswith('REPORT hit')]
    behind = []
    dsum = (f"{len(duty)} duties" + (' | ' + '; '.join(flags) if flags else '') + f"\n      monitoring ({e['service']['name']}): " + (', '.join(sorted(m.split(':')[0] for m in mon)) or 'ok')
            + (f"\n      office: " + ', '.join(behind) if behind else ''))
    res = f'no CDD in this sector on {ON}: no UBO question' if e.get('no_cdd') else \
          'no UBO rule modelled for this date (AMLR from 10 July 2027)' if e.get('no_rule') and not natural else \
          'natural person: no UBO test' if natural else (short(got) if got else 'nobody qualifies -> fallback: ' + ', '.join(x.split(' ', 1)[1] for x in fb))
    print(f"{'PASS' if passed else 'FAIL'}  {cid:<34} {e['supervisor']:<13} {e['scenario'][:58]:<58}  {res}")
    print(f"      {dsum}")
    if not passed:
        print(f"      expected: {short(e['ubo'])}  fallback: {e['fallback']}")
        if not mon_ok:
            print(f"      monitoring: got {sorted(mon)}, expected {e['monitoring']}")
        for k in sorted(set(duty) | set(e['duties'])):
            if not duty.get(k, '').startswith(e['duties'].get(k, '#')):
                print(f"      duty {k}: got {duty.get(k)!r}, expected {e['duties'].get(k)!r}")
# ---- the office files: the office itself and the overview of its client files ----
import subprocess as _sp
with contextlib.redirect_stdout(io.StringIO()):
    _sp.run([sys.executable, os.path.join(HERE, 'casefold', 'build_office.py'), '--tests', '--on', ON], check=True, capture_output=True)
offices = {}
for cid, e in EXP.items():
    if only and not any(cid[3:].startswith(o) for o in only):
        continue
    offices.setdefault(e['office_id'], []).append(cid)
o_ok = o_bad = 0
for oid, cids in sorted(offices.items()):
    odb = os.path.join(HERE, 'tests', 'offices', oid + '.rl')
    got = {r['duty_id']: r['status'].lower() for r in run(rel, odb, {}, command=QO1, read=True)}
    files = run(rel, odb, {}, read=True, command="MATCH (f:ClientFile) RETURN f.case AS case")
    shared = run(rel, odb, {}, read=True, command="MATCH (f:ClientFile)-[:HAS_COUNTERPARTY]->(k:CounterpartyKey) WITH k, count(DISTINCT f) AS n WHERE n > 1 RETURN count(k) AS n")[0]['n']
    exp_o = EXP[cids[0]]['office_records']
    passed = got == exp_o and sorted(f['case'] for f in files) == sorted(c for c in EXP if EXP[c]['office_id'] == oid) and shared == 1
    o_ok += passed; o_bad += not passed
    behind = ', '.join(k.split(':')[-1] + ' ' + v for k, v in got.items() if v != 'up to date')
    print(f"{'PASS' if passed else 'FAIL'}  office file {oid:<32} {len(files)} client files, {shared} shared counterparty" + (f" | behind: {behind}" if behind else ''))
    if not passed:
        print(f"      got {got}, expected {exp_o}")
print('per category: ' + ', '.join(f'{k}: {v[0]}/{sum(v)}' for k, v in sorted(by_cat.items())))
print(f"answers as of {ON}: client files {ok} passed, {bad} failed; office files {o_ok} passed, {o_bad} failed   (" + ', '.join(f'{k}: {v[0]}/{sum(v)}' for k, v in sorted(by_sup.items())) + ')')
sys.exit(1 if bad or o_bad else 0)
