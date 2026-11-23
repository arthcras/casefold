"""Focused crawl: start at one wallet, follow the widest flows hop by hop.

Like the money flow in the app: per wallet the `top` counterparties that moved the most, measured per asset relative to
the largest flow in that asset (so USDT and BTC can be compared), for `hops` steps, forward (out), backward (in) or both.
Lookalike tokens (asset ending in *) are kept as evidence but never followed.
"""
from collections import defaultdict
from .store import now


def trace(src, store, address, hops=3, top=5, direction='out', limit=100, max_age_hours=24, max_addresses=200, log=print):
    chain = src.chain
    hop = {address: 0}
    fetched, calls0 = [], getattr(src.http, 'calls', 0)
    frontier = [address]
    for h in range(hops + 1):
        nxt = []
        for a in frontier:
            if len(fetched) >= max_addresses:
                log(f'stopped at {max_addresses} addresses'); frontier = []; break
            if not store.fresh(chain, a, max_age_hours):
                ts = src.transfers(a, limit)
                store.save(chain, a, ts)
                log(f'{chain}:{a} hop {h}: {len(ts)} transfers fetched')
            fetched.append(a)
            if h == hops:
                continue
            flows = defaultdict(float)
            for t in store.of(chain, a):
                if t['asset'].endswith('*'):
                    continue
                if direction in ('out', 'both') and t['from'] == a and t['to'] != a:
                    flows[(t['to'], t['asset'])] += t['amount']
                if direction in ('in', 'both') and t['to'] == a and t['from'] != a:
                    flows[(t['from'], t['asset'])] += t['amount']
            mx = defaultdict(float)
            for (c, asset), v in flows.items():
                mx[asset] = max(mx[asset], v)
            best = {}
            for (c, asset), v in flows.items():
                rel = v / mx[asset] if mx[asset] else 0
                best[c] = max(best.get(c, 0), rel)
            for c, _ in sorted(best.items(), key=lambda kv: -kv[1])[:top]:
                if c not in hop:
                    hop[c] = h + 1; nxt.append(c)
        frontier = nxt
        if not frontier:
            break
    keys = set(fetched)
    seen, rows = set(), []
    for a in fetched:
        for t in store.of(chain, a):
            k = (t['tx'], t['from'], t['to'], t['asset'], t['amount'])
            if k in seen:
                continue
            seen.add(k)
            if t['from'] in keys or t['to'] in keys:
                rows.append({**t, 'hop': min(hop.get(t['from'], 99), hop.get(t['to'], 99)) + 1})
    rows.sort(key=lambda r: (r['time'] or '', r['tx'] or ''))
    return {'chain': chain, 'start': address, 'direction': direction, 'hops': hops, 'top': top, 'fetched_at': now(),
            'addresses': [{'key': f'{chain}:{a}', 'hop': hop[a]} for a in fetched], 'transfers': rows,
            'api_calls': getattr(src.http, 'calls', 0) - calls0}


def as_chain_file(result, name=None):
    """The trace in the format of data/crypto/chain/<entity>.json, so the static build (build_crypto.py) can use it too."""
    return {'entity': f"TRACE:{result['chain']}:{result['start']}", 'name': name or f"Trace of {result['start']}", 'fetched': result['fetched_at'],
            'seeds': [f"{result['chain']}:{result['start']}"], 'summaries': {a['key']: {'hop': a['hop']} for a in result['addresses']},
            'transfers': [{**{k: t[k] for k in ('hop', 'chain', 'tx', 'time', 'from', 'to', 'amount', 'asset', 'api')}, **({'contract': t['contract']} if t.get('contract') else {})}
                          for t in result['transfers']]}
