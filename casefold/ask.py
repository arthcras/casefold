#!/usr/bin/env python3
"""Run one of the questions in queries/ against a case file and print the answer as a table.

usage:  python3 casefold/ask.py cases/nl-kalmora.rl 01                 # missing documents and why
        python3 casefold/ask.py cases/nl-kalmora.rl 02 doctype=source_of_wealth
        python3 casefold/ask.py cases/nl-kalmora.rl 05                # KYCC still open
        python3 casefold/ask.py cases/nl-kalmora.rl 07 term=veto
        python3 casefold/ask.py --list
"""
import glob, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_case import find_relate, HERE

Q = sorted(glob.glob(os.path.join(HERE, 'queries', '*.cypher'))) + sorted(glob.glob(os.path.join(HERE, 'queries', 'office', '*.cypher'))) + sorted(glob.glob(os.path.join(HERE, 'queries', 'register', '*.cypher'))) + sorted(glob.glob(os.path.join(HERE, 'queries', 'explore', '*.cypher'))) + sorted(glob.glob(os.path.join(HERE, 'queries', 'law', '*.cypher')))
if '--list' in sys.argv or len(sys.argv) < 3:
    for q in Q:
        print(os.path.relpath(q, os.path.join(HERE, 'queries'))[:-7].split('_')[0], open(q, encoding='utf-8').readline().strip('/ \n'))
    sys.exit(0)
db, num, params = sys.argv[1], sys.argv[2], sys.argv[3:]
q = next((x for x in Q if (os.path.relpath(x, os.path.join(HERE, 'queries'))[:-7] if '/' in num else os.path.basename(x)).startswith(num if '/' in num else num.zfill(2))), None) or sys.exit(f'no query {num}; use --list')
args = [find_relate(os.environ.get('RELATE_BIN')), 'query', '--database', db, '--read-only', '--mode', 'table', '--max-rows', '0']
import json, re
for p in params:
    k, _, v = p.partition('=')
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', v):
        v = json.dumps(v)                       # a date is a string, not a number
    args += ['--param', f'{k}={v}']
if '$on' in open(q, encoding='utf-8').read() and not any(p.startswith('on=') for p in params):
    import datetime
    args += ['--param', 'on=' + json.dumps(datetime.date.today().isoformat())]      # rules valid today unless on=YYYY-MM-DD is given
print(open(q, encoding='utf-8').readline().strip('/ \n'))
r = subprocess.run(args, input=open(q, encoding='utf-8').read(), capture_output=True, text=True)
print('\n'.join(l for l in (r.stdout or r.stderr).splitlines() if not l.lstrip().startswith(('timings', '{"elapsed', 'planCache', 'miss', 'hit')) or l.startswith('|')))
