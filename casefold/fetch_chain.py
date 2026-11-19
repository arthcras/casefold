#!/usr/bin/env python3
"""Trace listed crypto addresses on chain (needs internet; run by the chain workflow).

For each entity in data/crypto/chain_seeds.json: every crypto address the sanctions lists give for it, its latest
transfers (hop 1), and for the largest counterparties their own latest transfers (hop 2). Public explorers, no keys:
  bitcoin   mempool.space            /api/address/<a>/txs
  ethereum  eth.blockscout.com       /api/v2/addresses/<a>/token-transfers and /transactions
  tron      api.trongrid.io          /v1/accounts/<a>/transactions/trc20 and /transactions
Writes data/crypto/chain/<entity>.json: the transfers (chain, tx, time, from, to, amount, asset, api) and per address a
summary. A transfer is a fact from the chain; who controls an address that is not on a list is not known here.
"""
import datetime, json, os, sys, time, urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, 'data', 'crypto', 'chain')


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'casefold-chain/1.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            if i == tries - 1:
                print(f'  failed {url}: {e}', file=sys.stderr); return None
            time.sleep(2 + 3 * i)


def btc(addr, n):
    txs = get(f'https://mempool.space/api/address/{addr}/txs') or []
    out = []
    for t in txs[:n]:
        when = (t.get('status') or {}).get('block_time')
        ins = [v.get('prevout') or {} for v in t.get('vin', [])]
        outs = t.get('vout', [])
        in_addrs = [i.get('scriptpubkey_address') for i in ins if i.get('scriptpubkey_address')]
        if addr in in_addrs:      # the address pays: one flow per output to another address
            for o in outs:
                a = o.get('scriptpubkey_address')
                if a and a != addr and a not in in_addrs:
                    out.append(('bitcoin', t['txid'], when, addr, a, o['value'] / 1e8, 'BTC', 'mempool.space'))
        else:                      # the address receives: the value it got, from the first input address
            got = sum(o['value'] for o in outs if o.get('scriptpubkey_address') == addr)
            if got and in_addrs:
                out.append(('bitcoin', t['txid'], when, in_addrs[0], addr, got / 1e8, 'BTC', 'mempool.space'))
    s = get(f'https://mempool.space/api/address/{addr}') or {}
    cs = s.get('chain_stats') or {}
    summ = {'received': cs.get('funded_txo_sum', 0) / 1e8, 'sent': cs.get('spent_txo_sum', 0) / 1e8, 'tx_count': cs.get('tx_count'), 'asset': 'BTC'}
    return out, summ


def eth(addr, n):
    out = []
    tt = get(f'https://eth.blockscout.com/api/v2/addresses/{addr}/token-transfers?type=ERC-20') or {}
    for x in (tt.get('items') or [])[:n]:
        tot = x.get('total') or {}; tok = x.get('token') or {}
        try:
            amt = int(tot.get('value') or 0) / 10 ** int(tot.get('decimals') or tok.get('decimals') or 18)
        except Exception:
            continue
        ts = x.get('timestamp'); when = int(datetime.datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp()) if ts else None
        out.append(('ethereum', x.get('transaction_hash'), when, (x.get('from') or {}).get('hash'), (x.get('to') or {}).get('hash'), amt, tok.get('symbol') or '?', 'blockscout'))
    tx = get(f'https://eth.blockscout.com/api/v2/addresses/{addr}/transactions') or {}
    for x in (tx.get('items') or [])[:n]:
        v = int(x.get('value') or 0) / 1e18
        if not v:
            continue
        ts = x.get('timestamp'); when = int(datetime.datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp()) if ts else None
        out.append(('ethereum', x.get('hash'), when, (x.get('from') or {}).get('hash'), (x.get('to') or {}).get('hash'), v, 'ETH', 'blockscout'))
    s = get(f'https://eth.blockscout.com/api/v2/addresses/{addr}') or {}
    summ = {'balance': int(s.get('coin_balance') or 0) / 1e18, 'asset': 'ETH', 'is_contract': s.get('is_contract')}
    return out, summ


def trx(addr, n):
    out = []
    tt = get(f'https://api.trongrid.io/v1/accounts/{addr}/transactions/trc20?limit={n}&only_confirmed=true') or {}
    for x in tt.get('data') or []:
        ti = x.get('token_info') or {}
        try:
            amt = int(x.get('value') or 0) / 10 ** int(ti.get('decimals') or 6)
        except Exception:
            continue
        out.append(('tron', x.get('transaction_id'), (x.get('block_timestamp') or 0) // 1000, x.get('from'), x.get('to'), amt, ti.get('symbol') or '?', 'trongrid'))
    time.sleep(1.2)   # trongrid without a key: keep under its rate limit
    s = get(f'https://api.trongrid.io/v1/accounts/{addr}') or {}
    d = (s.get('data') or [{}])
    d = d[0] if d else {}
    summ = {'balance': (d.get('balance') or 0) / 1e6, 'asset': 'TRX', 'created': (d.get('create_time') or 0) // 1000 or None}
    time.sleep(1.2)
    return out, summ


FETCH = {'bitcoin': btc, 'ethereum': eth, 'tron': trx}


def main():
    cfg = json.load(open(os.path.join(HERE, 'data', 'crypto', 'chain_seeds.json'), encoding='utf-8'))
    listed = {}
    for f in os.listdir(os.path.join(HERE, 'data', 'crypto', 'sanctions')):
        for e in json.load(open(os.path.join(HERE, 'data', 'crypto', 'sanctions', f), encoding='utf-8'))['entries']:
            if e['addresses']:
                listed[e['id']] = e
    os.makedirs(OUT, exist_ok=True)
    n = cfg['max_transfers_per_address']
    for eid in cfg['entities']:
        e = listed.get(eid)
        if not e:
            print(f'{eid}: not on an imported list', file=sys.stderr); continue
        transfers, summaries, seen = [], {}, set()
        seeds = [(a['chain'], a['address']) for a in e['addresses'] if a['chain'] in FETCH]
        for chain, a in seeds:
            t, s = FETCH[chain](a, n); transfers += [(1,) + x for x in t]; summaries[f'{chain}:{a}'] = {**s, 'hop': 0}; seen.add(a)
            print(f'{eid} {chain}:{a}: {len(t)} transfers')
        # hop 2: the counterparties that moved the most value (per asset count), their own latest transfers
        vol = defaultdict(float)
        for x in transfers:
            for side in (x[4], x[5]):
                if side and side not in seen:
                    vol[(x[1], side)] += x[6]
        top = sorted(vol.items(), key=lambda kv: -kv[1])[:cfg['hop2_counterparties']]
        for (chain, a), _ in top:
            t, s = FETCH[chain](a, 25); transfers += [(2,) + x for x in t]; summaries[f'{chain}:{a}'] = {**s, 'hop': 1}; seen.add(a)
            print(f'{eid} hop 2 {chain}:{a}: {len(t)} transfers')
        rows, dup = [], set()
        for h, chain, tx, when, fr, to, amt, asset, api in transfers:
            k = (chain, tx, fr, to, asset, round(amt, 8))
            if not fr or not to or k in dup:
                continue
            dup.add(k)
            rows.append({'hop': h, 'chain': chain, 'tx': tx, 'time': datetime.datetime.fromtimestamp(when, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ') if when else None,
                         'from': fr, 'to': to, 'amount': round(amt, 8), 'asset': asset, 'api': api})
        rows.sort(key=lambda r: (r['chain'], r['time'] or '', r['tx'] or ''))
        rec = {'entity': eid, 'name': e['name'], 'fetched': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
               'seeds': [f'{c}:{a}' for c, a in seeds], 'summaries': summaries, 'transfers': rows}
        json.dump(rec, open(os.path.join(OUT, eid.replace(':', '-') + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        print(f'{eid}: {len(rows)} transfers kept')


if __name__ == '__main__':
    main()
