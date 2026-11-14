#!/usr/bin/env python3
"""Long-term memory: approve a pattern that reason.py proposed in a case, and keep it in the shared store memory/longterm.rl.

The shared store is a Relate file of its own. It holds approved patterns only: an id, a title, why it matters, the
proposed action and a read-only Cypher test, plus how many cases it was seen in. No names, no amounts, no case data:
the case is counted by a one-way hash. reason.py tests every approved pattern against each case file.

usage:  python3 casefold/memory.py approve cases/nl-kalmora.rl P-high-risk-counterparty-kycc-open
        python3 casefold/memory.py list
        python3 casefold/memory.py sessions cases/nl-kalmora.rl         # short-term: sessions still open
        python3 casefold/memory.py expire cases/nl-kalmora.rl           # drop expired sessions (episodes and patterns stay)
"""
import hashlib, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_case import find_relate, HERE
from embed import relate_rows, relate_write

STORE = os.path.join(HERE, 'memory', 'longterm.rl')
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def main():
    rel = find_relate(os.environ.get('RELATE_BIN'))
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    if cmd == 'approve':
        case, pid = sys.argv[2], sys.argv[3]
        p = relate_rows(rel, case, f"MATCH (p:Pattern {{id:'{pid}'}}) RETURN p.id AS id, p.title AS title, p.why AS why, p.action AS action, p.test AS test")
        if not p:
            sys.exit(f'no pattern {pid} in {case}')
        cid = relate_rows(rel, case, 'MATCH (k:Case) RETURN k.id AS id')[0]['id']
        h = hashlib.sha256(cid.encode()).hexdigest()[:12]
        relate_write(rel, case, "MATCH (p:Pattern {id:$id}) SET p.status='approved', p.approved=$now", {'id': pid, 'now': NOW})
        relate_write(rel, STORE, """
MERGE (x:Pattern {id:$p.id}) ON CREATE SET x.created=$now, x.cases=[]
SET x.title=$p.title, x.why=$p.why, x.action=$p.action, x.test=$p.test, x.status='approved', x.kind='long-term', x.approved=$now,
    x.cases = CASE WHEN $h IN x.cases THEN x.cases ELSE x.cases + $h END
SET x.seen = size(x.cases)""", {'p': p[0], 'now': NOW, 'h': h})
        print(f'{pid} approved and stored in {os.path.relpath(STORE)} (case counted as {h})')
    elif cmd == 'list':
        if not os.path.exists(STORE):
            print('long-term memory is empty'); return
        for r in relate_rows(rel, STORE, "MATCH (p:Pattern) RETURN p.id AS id, p.status AS status, p.seen AS seen, p.title AS title ORDER BY id"):
            print(f"{r['id']}  [{r['status']}, seen in {r['seen']} case(s)]\n    {r['title']}")
    elif cmd == 'sessions':
        for r in relate_rows(rel, sys.argv[2], "MATCH (s:Session)-[:ASKED]->(q:Ask)-[:ANSWERED_BY]->(a:Answer) WHERE s.expires > $now RETURN s.id AS session, s.expires AS expires, q.text AS asked, a.text AS answer ORDER BY session, asked".replace('$now', f"'{NOW}'")):
            print(f"{r['session']} (until {r['expires']})\n  Q: {r['asked']}\n  A: {r['answer'][:160]}")
    elif cmd == 'expire':
        relate_write(rel, sys.argv[2], """
MATCH (s:Session) WHERE s.expires <= $now OPTIONAL MATCH (s)-[:ASKED]->(q:Ask) DETACH DELETE s, q""", {'now': NOW})
        print('expired sessions removed (answers, steps, episodes and patterns are kept)')
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
