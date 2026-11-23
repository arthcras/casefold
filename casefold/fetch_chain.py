#!/usr/bin/env python3
"""Trace listed crypto addresses on chain (needs internet; run by the chain workflow).

For each entity in data/crypto/chain_seeds.json: every crypto address the sanctions lists give for it, its latest
transfers (hop 1), and for the largest counterparties their own latest transfers (hop 2). Public explorers, no keys:
  bitcoin   mempool.space            /api/address/<a>/txs
  ethereum  eth.blockscout.com       /api/v2/addresses/<a>/token-transfers and /transactions
  tron      api.trongrid.io          /v1/accounts/<a>/transactions/trc20 and /transactions
An asset marked * is a token that only carries the name (not the known USDT or USDC contract): kept, but not counted.
Writes data/crypto/chain/<entity>.json: the transfers (chain, tx, time, from, to, amount, asset, api) and per address a
summary. A transfer is a fact from the chain; who controls an address that is not on a list is not known here.
"""
import datetime, json, os, sys, time, urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# token contracts taken as the real asset; any other token with the same symbol is a copy (spam or a lookalike)
KNOWN = {'0xdac17f958d2ee523a2206206994597c13d831ec7': 'USDT', '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': 'USDC',
         'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t': 'USDT', 'TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8': 'USDC'}
OUT = os.path.join(HERE, 'data', 'crypto', 'chain')


def get(url, tries=4, headers=None):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'casefold-chain/1.0', 'Accept': 'application/json', **(headers or {})})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            if getattr(e, 'code', None) in (401, 403, 404) or i == tries - 1:
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
        c = (tok.get('address_hash') or tok.get('address') or '').lower()
        out.append(('ethereum', x.get('transaction_hash'), when, (x.get('from') or {}).get('hash'), (x.get('to') or {}).get('hash'), amt, KNOWN.get(c) or (tok.get('symbol') or '?') + '*', 'blockscout'))
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
        out.append(('tron', x.get('transaction_id'), (x.get('block_timestamp') or 0) // 1000, x.get('from'), x.get('to'), amt, KNOWN.get(ti.get('address') or '') or (ti.get('symbol') or '?') + '*', 'trongrid'))
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
        out = os.path.join(OUT, eid.replace(':', '-') + '.json')
        if os.path.exists(out) and '--refresh' not in sys.argv:
            print(f'{eid}: already traced, skipped (use --refresh to trace again)'); continue
        seeds = [(a['chain'], a['address']) for a in e['addresses'] if a['chain'] in FETCH][:cfg.get('max_seed_addresses', 15)]
        for chain, a in seeds:
            t, s = FETCH[chain](a, n); transfers += [(1,) + x for x in t]; summaries[f'{chain}:{a}'] = {**s, 'hop': 0}; seen.add(a)
            print(f'{eid} {chain}:{a}: {len(t)} transfers')
        # hop 2: the counterparties that moved the most value (per asset count), their own latest transfers
        vol = defaultdict(float)
        for x in transfers:
            if x[7].endswith('*'):
                continue
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


def tags_of(obj, path=''):
    """Every string under a key that names a tag or a label, from an explorer's address record."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = k.lower()
            if isinstance(v, str) and v.strip() and any(w in kl for w in ('tag', 'label', 'name')) and not kl.endswith(('logo', 'url', 'hash', 'icon')) and kl not in ('token_name',):
                out.append((path + k, v.strip()))
            elif isinstance(v, (dict, list)) and kl not in ('tokens', 'token_balances', 'trc20token_balances', 'withPriceTokens', 'balances'):
                out += tags_of(v, path + k + '.')
    elif isinstance(obj, list):
        for x in obj[:20]:
            out += tags_of(x, path)
    return out


def labels():
    """Labels the public explorers give for the addresses in the traces: Blockscout (ethereum) and Tronscan (tron).
    Bitcoin has no public label service here. Writes data/crypto/chain/labels.json."""
    addrs = set()
    for f in os.listdir(OUT):
        if f.endswith('.json') and not f.startswith('labels'):
            r = json.load(open(os.path.join(OUT, f), encoding='utf-8'))
            for t in r['transfers']:
                if not t['asset'].endswith('*'):
                    addrs |= {(t['chain'], t['from']), (t['chain'], t['to'])}
    out = {}
    for chain, a in sorted(addrs):
        if chain == 'ethereum':
            r = get(f'https://eth.blockscout.com/api/v2/addresses/{a}', tries=2) or {}
            tags = [(k, v) for k, v in tags_of({'name': r.get('name'), 'metadata': r.get('metadata'), 'public_tags': r.get('public_tags'), 'private_tags': r.get('private_tags')})]
            src = 'blockscout'
            extra = {'is_contract': r.get('is_contract'), 'is_scam': r.get('is_scam')}
        elif chain == 'tron':
            key = os.environ.get('TRONSCAN_API_KEY')
            if not key:      # Tronscan now asks for a (free) API key: without it, tron addresses stay unlabelled
                continue
            r = get(f'https://apilist.tronscanapi.com/api/accountv2?address={a}', tries=2, headers={'TRON-PRO-API-KEY': key}) or {}
            keep = {k: r.get(k) for k in r if any(w in k.lower() for w in ('tag', 'risk', 'label'))}
            tags = tags_of(keep); src = 'tronscan'
            extra = {k: v for k, v in keep.items() if isinstance(v, (bool, int)) and v}
            time.sleep(0.4)
        else:
            continue
        tags = [(k, v) for k, v in tags if v and v.lower() not in ('none', 'null')]
        if tags or any(extra.values()):
            out[f'{chain}:{a}'] = {'source': src, 'tags': [{'field': k, 'text': v} for k, v in tags][:8], **{k: v for k, v in extra.items() if v}}
    tron_key = bool(os.environ.get('TRONSCAN_API_KEY'))
    json.dump({'tron_labels': 'tronscan' if tron_key else 'not fetched: set TRONSCAN_API_KEY', 'note': 'Address labels as given by public explorers (Blockscout for ethereum, Tronscan for tron), fetched with the traces. A label is the explorer\'s attribution, not ours; it is shown with its source.',
               'fetched': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'checked': len(addrs), 'labels': dict(sorted(out.items()))},
              open(os.path.join(OUT, 'labels.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'labels: {len(out)} of {len(addrs)} addresses labelled')


if __name__ == '__main__':
    if '--labels-only' not in sys.argv:
        main()
    if '--labels' in sys.argv or '--labels-only' in sys.argv:
        labels()
