"""Trace one wallet from the command line (needs internet).

  python3 -m casefold.crawler tron TNDjh6WGLYyWmkh8vfu42bXVHUqFNQ3rDq --hops 2 --top 5 [--out data/crypto/chain] [--db crawler.sqlite]
Prints a summary; with --out also writes the trace as a data/crypto/chain file for the static build.
"""
import argparse, json, os

from .crawl import as_chain_file, trace
from .sources import sources
from .store import Store

ap = argparse.ArgumentParser()
ap.add_argument('chain'); ap.add_argument('address')
ap.add_argument('--hops', type=int, default=2); ap.add_argument('--top', type=int, default=5)
ap.add_argument('--direction', default='out', choices=['out', 'in', 'both']); ap.add_argument('--limit', type=int, default=50)
ap.add_argument('--db', default=':memory:'); ap.add_argument('--out')
a = ap.parse_args()
r = trace(sources()[a.chain], Store(a.db), a.address, a.hops, a.top, a.direction, a.limit)
assets = {}
for t in r['transfers']:
    assets[t['asset']] = assets.get(t['asset'], 0) + 1
tokens = {}
for t in r['transfers']:
    if t['asset'].endswith('*') and t.get('contract'):
        tokens.setdefault(t['asset'], set()).add(t['contract'])
print(json.dumps({'unverified_tokens': {k: sorted(v) for k, v in tokens.items()}}, indent=1))
print(json.dumps({'start': r['start'], 'addresses': len(r['addresses']), 'transfers': len(r['transfers']), 'api_calls': r['api_calls'],
                  'assets': dict(sorted(assets.items(), key=lambda kv: -kv[1])[:8])}, indent=1))
if a.out:
    os.makedirs(a.out, exist_ok=True)
    f = os.path.join(a.out, f'trace-{a.chain}-{a.address}.json')
    json.dump(as_chain_file(r), open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('written', f)
