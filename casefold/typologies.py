"""Transaction typologies: fixed rules over the traced transfers that label wallets and transfers.

The rules and their thresholds are in data/crypto/tx_typologies.json. Every label is a lead for review, not proof.
Output for the graph (same Cypher on Relate and Neo4j):
  tt  the typologies              -> (:TxTypology)
  tl  wallet labels               -> (:Address)-[:SHOWS {asset, evidence, first, last, n}]->(:TxTypology)
  te  transfer labels             -> SENT.typologies (list of ids)
  tg  typology -> guidance links  -> (:TxTypology)-[:FLAGGED_IN {section, page, says}]->(:Guidance)
"""
import json, os, re
from collections import defaultdict
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STABLE = {'USDT', 'USDC'}
SERVICE = {'exchange', 'licensed_exchange', 'defi', 'p2p_exchange', 'high_risk_exchange'}


def _t(s):
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except ValueError:
        return None


def rule_text(rule, params):
    def show(v):
        return ', '.join(f"{n:g} {k}" for k, n in v.items()) if isinstance(v, dict) else f"{v}"
    return re.sub(r'\{(\w+)\}', lambda m: show(params.get(m.group(1))), rule)


def _body(addr):
    """The part of an address a person compares by eye: without the fixed chain prefix (0x, bc1, T, 1, 3)."""
    a = str(addr).split(':')[-1]
    if a[:2].lower() == '0x':
        return a[2:].lower()
    if a[:3].lower() in ('bc1', 'ltc'):
        return a[3:].lower()
    return a[1:]


def _same(a, b, prefix, suffix, long_suffix):
    a, b = _body(a), _body(b)
    if a == b or len(a) < 8 or len(b) < 8:
        return False
    return (a[-suffix:] == b[-suffix:] and a[:prefix] == b[:prefix]) or a[-long_suffix:] == b[-long_suffix:]


def raw_transfers():
    """Every traced transfer, lookalike tokens included (asset ending in *), with its time."""
    d = os.path.join(HERE, 'data', 'crypto', 'chain')
    out, seen = [], set()
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if f.startswith('labels') or not f.endswith('.json'):
            continue
        for t in json.load(open(os.path.join(d, f), encoding='utf-8')).get('transfers', []):
            k = (t.get('tx'), t['from'], t['to'], t['asset'], t['amount'])
            if k in seen or not (0 < t['amount'] < 1e12):
                continue
            seen.add(k)
            out.append({**t, 'fk': t['chain'] + ':' + t['from'], 'tk': t['chain'] + ':' + t['to'], 'ts': _t(t.get('time'))})
    return out


def detect(listed_keys, labels, categories, transfers=None):
    """listed_keys: set of address keys on a sanctions list; labels: {key: category id}; categories: {id: severity}."""
    cfg = json.load(open(os.path.join(HERE, 'data', 'crypto', 'tx_typologies.json'), encoding='utf-8'))
    P = {t['id']: t.get('params', {}) for t in cfg['typologies']}
    ins = json.load(open(os.path.join(HERE, 'data', 'crypto', 'instruments.json'), encoding='utf-8'))['instruments']
    banned = {(i['chain'], i['symbol']): i['sanctioned'] for i in ins if i.get('sanctioned')}
    T = raw_transfers() if transfers is None else [{**t, 'fk': t['chain'] + ':' + t['from'], 'tk': t['chain'] + ':' + t['to'], 'ts': _t(t.get('time'))} for t in transfers if t.get('from') and t.get('to') and 0 < t['amount'] < 1e12]
    clean = [t for t in T if not t['asset'].endswith('*')]
    DUST = P.get('TT-POISON', {}).get('dust', {})
    def dusty(t):
        return t['asset'] in DUST and t['amount'] <= DUST[t['asset']]
    wl = defaultdict(lambda: {'n': 0, 'first': None, 'last': None, 'evidence': ''})     # (key, typology, asset) -> label
    el = defaultdict(set)                                                                 # (from, to, asset) -> typologies

    def wlabel(key, tid, asset, ev, ts=None, n=1):
        x = wl[(key, tid, asset)]
        x['n'] += n
        x['evidence'] = x['evidence'] or ev
        for s in [ts] if ts else []:
            x['first'] = min(x['first'], s) if x['first'] else s
            x['last'] = max(x['last'], s) if x['last'] else s

    lab = {k.lower(): v for k, v in labels.items()}
    for t in clean:
        e = (t['fk'], t['tk'], t['asset'])
        if t['fk'] in listed_keys or t['tk'] in listed_keys:
            el[e].add('TT-LISTED')
        for k in (t['fk'], t['tk']):
            c = lab.get(k.lower())
            if c == 'sanctions':
                el[e].add('TT-LISTED')
            elif c in SERVICE:
                el[e].add('TT-SERVICE')
            elif c and categories.get(c) in ('high', 'severe'):
                el[e].add('TT-HIGHRISK')
        if t['asset'] in STABLE and t['amount'] >= P['TT-LARGE'].get('usd', 100000):
            el[e].add('TT-LARGE')
    # sanctioned instruments: the symbol as the explorer gives it (unverified contract: asset ends in *)
    for t in T:
        sym = t['asset'].rstrip('*')
        if (t['chain'], sym) in banned:
            b = banned[(t['chain'], sym)]
            when = 'after' if str(t.get('time') or '')[:10] >= b['from'] else 'before'
            note = f"{'contract not verified' if t['asset'].endswith('*') else 'verified contract'}; {when} the {b['by']} ban of {b['from']}"
            wlabel(t['tk'], 'TT-SANCTIONED-ASSET', sym, f"received {sym} ({note})", t['ts'])
            wlabel(t['fk'], 'TT-SANCTIONED-ASSET', sym, f"sent {sym} ({note})", t['ts'])
    # lookalike or spam tokens: an unverified token whose name imitates a known asset or advertises
    known = re.compile(r'USDT|USDC|ETH|BTC|TRX|TETHER', re.I)
    advert = re.compile(r'TG\b|t\.me|https?|www\.|\.(com|org|io|net|xyz|top|cc|vip)\b|claim|reward|airdrop|visit|gift|bonus|解冻|领取', re.I)
    def lookalike(name):
        return bool(re.search(r'[^\x20-\x7e]', name)) or bool(advert.search(name)) or (bool(known.search(name)) and name.upper() not in {'WETH', 'WBTC', 'STETH', 'WSTETH'})
    spam = defaultdict(list)
    for t in T:
        nm = t['asset'].rstrip('*')
        if t['asset'].endswith('*') and (t['chain'], nm) not in banned and lookalike(nm):
            spam[t['tk']].append(t)
    for k, xs in spam.items():
        if len(xs) >= P['TT-LOOKALIKE'].get('min', 3):
            names = sorted({x['asset'].rstrip('*') for x in xs})[:4]
            for x in xs:
                wlabel(k, 'TT-LOOKALIKE', 'token', f"{len(xs)} transfers of lookalike or spam tokens ({', '.join(names)})", x['ts'])
    by_out, by_in = defaultdict(list), defaultdict(list)
    for t in clean:
        if t['ts']:
            by_out[(t['fk'], t['asset'])].append(t)
            by_in[(t['tk'], t['asset'])].append(t)
    # fan-out and fan-in: distinct counterparties within a sliding window
    for tid, groups, side in (('TT-FANOUT', by_out, 'tk'), ('TT-FANIN', by_in, 'fk')):
        mn, h = P[tid].get('min', 10), timedelta(hours=P[tid].get('hours', 72))
        for (key, asset), xs in groups.items():
            xs = sorted(xs, key=lambda x: x['ts'])
            j = 0
            for i in range(len(xs)):
                while xs[i]['ts'] - xs[j]['ts'] > h:
                    j += 1
                cps = {x[side] for x in xs[j:i + 1]}
                if len(cps) >= mn:
                    wlabel(key, tid, asset, f"{'sent to' if tid == 'TT-FANOUT' else 'received from'} {len(cps)} wallets within {P[tid].get('hours')} h", xs[i]['ts'], len(cps))
                    for x in xs[j:i + 1]:
                        el[(x['fk'], x['tk'], x['asset'])].add(tid)
                    break
    # pass-through: most of an incoming amount leaves again within the window
    h, ratio = timedelta(hours=P['TT-PASS'].get('hours', 24)), P['TT-PASS'].get('ratio', 0.8)
    for (key, asset), ins_ in by_in.items():
        outs = sorted(by_out.get((key, asset), []), key=lambda x: x['ts'])
        if not outs:
            continue
        for x in sorted(ins_, key=lambda x: x['ts']):
            if dusty(x):
                continue
            nxt = [o for o in outs if x['ts'] <= o['ts'] <= x['ts'] + h]
            s = sum(o['amount'] for o in nxt)
            if x['amount'] > 0 and s >= ratio * x['amount']:
                wlabel(key, 'TT-PASS', asset, f"received {x['amount']:,.2f} {asset}; within {P['TT-PASS'].get('hours')} h it sent {s:,.2f} {asset} on", x['ts'])
                el[(x['fk'], x['tk'], asset)].add('TT-PASS')
                for o in nxt:
                    el[(o['fk'], o['tk'], asset)].add('TT-PASS')
    # structuring: repeated stablecoin transfers just below a threshold between the same two wallets
    p = P['TT-STRUCT']
    pairs = defaultdict(list)
    for t in clean:
        if t['asset'] in STABLE and t['ts']:
            for thr in p.get('thresholds', [1000, 10000]):
                if p.get('band', .85) * thr <= t['amount'] < thr:
                    pairs[(t['fk'], t['tk'], t['asset'], thr)].append(t)
    for (a, b, asset, thr), xs in pairs.items():
        xs = sorted(xs, key=lambda x: x['ts'])
        for i in range(len(xs)):
            win = [x for x in xs[i:] if x['ts'] - xs[i]['ts'] <= timedelta(days=p.get('days', 7))]
            if len(win) >= p.get('count', 3):
                wlabel(a, 'TT-STRUCT', asset, f"{len(win)} transfers to {b.split(':')[-1][:10]}… just below {thr:,} {asset} within {p.get('days')} days", win[0]['ts'], len(win))
                el[(a, b, asset)].add('TT-STRUCT')
                break
    # swap: one asset in, another out within the window
    d = timedelta(days=P['TT-SWAP'].get('days', 7))
    ins_by_key, outs_by_key = defaultdict(list), defaultdict(list)
    for (k, a), xs in by_in.items():
        ins_by_key[k] += xs
    for (k, a), xs in by_out.items():
        outs_by_key[k] += xs
    for k, ins_ in ins_by_key.items():
        for x in ins_:
            o = next((o for o in outs_by_key.get(k, []) if o['asset'] != x['asset'] and x['ts'] <= o['ts'] <= x['ts'] + d), None)
            if o:
                wlabel(k, 'TT-SWAP', f"{x['asset']}>{o['asset']}", f"received {x['asset']}, sent {o['asset']} within {P['TT-SWAP'].get('days')} days", x['ts'])
                el[(x['fk'], x['tk'], x['asset'])].add('TT-SWAP')
                el[(o['fk'], o['tk'], o['asset'])].add('TT-SWAP')
                break
    # peeling chain (Bitcoin): one big output on to a new wallet, a small one elsewhere, several times in a row
    share, hops = P['TT-PEEL'].get('share', .75), P['TT-PEEL'].get('hops', 3)
    txs = defaultdict(list)
    for t in clean:
        if t['chain'] == 'bitcoin' and t.get('tx'):
            txs[t['tx']].append(t)
    step = {}                      # from-key -> (next key, time) where the tx peels
    for tx, outs in txs.items():
        frm = {o['fk'] for o in outs}
        if len(frm) != 1 or len(outs) < 2:
            continue
        tot = sum(o['amount'] for o in outs)
        big = max(outs, key=lambda o: o['amount'])
        if tot > 0 and big['amount'] >= share * tot and big['tk'] not in frm:
            step[big['fk']] = (big['tk'], big['ts'], tx)
    for start in list(step):
        chain, k = [start], start
        while k in step and len(chain) < 50:
            k = step[k][0]
            if k in chain:
                break
            chain.append(k)
        if len(chain) - 1 >= hops:
            for a in chain[:-1]:
                wlabel(a, 'TT-PEEL', 'BTC', f"part of a peeling chain of {len(chain) - 1} steps", step[a][1])
                el[(a, step[a][0], 'BTC')].add('TT-PEEL')
    # round trip: back to the start within a few hops, same asset (on the summed flows)
    nxt = defaultdict(set)
    for t in clean:
        if not dusty(t):
            nxt[(t['fk'], t['asset'])].add(t['tk'])
    for (a, asset), bs in sorted(nxt.items()):
        for b in sorted(bs):
            if a in nxt.get((b, asset), ()):
                el[(a, b, asset)].add('TT-ROUND'); el[(b, a, asset)].add('TT-ROUND')
                wlabel(a, 'TT-ROUND', asset, f"sent {asset} to {b.split(':')[-1][:10]}… and received {asset} back")
            elif P['TT-ROUND'].get('hops', 3) >= 3:
                for c in sorted(nxt.get((b, asset), ())):
                    if c != a and a in nxt.get((c, asset), ()):
                        for e in ((a, b), (b, c), (c, a)):
                            el[(e[0], e[1], asset)].add('TT-ROUND')
                        wlabel(a, 'TT-ROUND', asset, f"{asset} returned in 3 hops via {b.split(':')[-1][:8]}… and {c.split(':')[-1][:8]}…")
                        break
    # address poisoning: dust or a fake token from an address that copies a real counterparty of the wallet
    p = P.get('TT-POISON')
    if p:
        tiny = lambda t: t['asset'].endswith('*') or dusty(t)
        real, small = defaultdict(set), defaultdict(list)          # wallet -> real counterparties; wallet -> dust transfers
        for t in T:
            for me, other in ((t['fk'], t['tk']), (t['tk'], t['fk'])):
                (small[me].append((other, t)) if tiny(t) else real[me].add(other))
        for me, xs in small.items():
            for other, t in xs:
                twin = next((c for c in sorted(real[me]) if c.split(':')[0] == other.split(':')[0] and _same(c, other, p.get('prefix', 2), p.get('suffix', 4), p.get('long_suffix', 6))), None)
                if not twin:
                    continue
                c, o = twin.split(':')[-1], other.split(':')[-1]
                what = f"a fake token ({t['amount']:g} {t['asset'].rstrip('*')})" if t['asset'].endswith('*') else f"dust ({t['amount']:g} {t['asset']})"
                wlabel(other, 'TT-POISON', 'any', f"{o[:6]}…{o[-6:]} imitates {c[:6]}…{c[-6:]}, a real counterparty of {me.split(':')[-1][:8]}…; {what}", t['ts'])
                if not t['asset'].endswith('*'):
                    el[(t['fk'], t['tk'], t['asset'])].add('TT-POISON')
                paid = [x for x in clean if x['fk'] == me and x['tk'] == other and not tiny(x)]
                if paid:
                    wlabel(me, 'TT-POISON', 'any', f"sent {sum(x['amount'] for x in paid):,.2f} {paid[0]['asset']} to the lookalike {o[:6]}…{o[-6:]}: the poisoning may have worked", paid[0]['ts'], len(paid))
                    for x in paid:
                        el[(x['fk'], x['tk'], x['asset'])].add('TT-POISON')
    tl = [{'key': k, 'typology': tid, 'asset': a, 'evidence': v['evidence'], 'n': v['n'],
           'first': v['first'].isoformat()[:19] if v['first'] else None, 'last': v['last'].isoformat()[:19] if v['last'] else None}
          for (k, tid, a), v in sorted(wl.items())]
    te = [{'from_key': a, 'to_key': b, 'asset': s, 'typologies': sorted(v)} for (a, b, s), v in sorted(el.items())]
    tt = [{k: t.get(k) for k in ('id', 'name', 'severity', 'level')} | {'rule': rule_text(t['rule'], t.get('params', {})), 'rule_template': t['rule'], 'params': t.get('params', {})}
          for t in cfg['typologies']]
    tg = cfg.get('guidance', [])
    return tt, tl, te, tg


LOAD = [
    "UNWIND $tt AS x MERGE (t:TxTypology {id: x.id}) SET t.name = x.name, t.severity = x.severity, t.level = x.level, t.rule = x.rule",
    "UNWIND $gd AS x MERGE (g:Guidance {id: x.id}) SET g.title = x.title, g.issuer = x.issuer_name, g.date = x.date, g.url = x.url, g.kind = x.kind, g.status = x.status, g.summary = x.summary, g.verify = x.verify, g.applies_from = x.applies_from",
    "UNWIND $gd AS x MATCH (g:Guidance {id: x.id}) MATCH (r:Regulator {id: x.issuer}) MERGE (r)-[:ISSUED]->(g)",
    "UNWIND $tg AS x MATCH (t:TxTypology {id: x.typology}) MATCH (g:Guidance {id: x.guidance}) MERGE (t)-[r:FLAGGED_IN {section: x.section}]->(g) SET r.page = x.page, r.says = x.says",
    "UNWIND $tl AS x MERGE (a:Address {key: x.key}) ON CREATE SET a.chain = split(x.key, ':')[0], a.address = split(x.key, ':')[1] WITH x, a MATCH (t:TxTypology {id: x.typology}) MERGE (a)-[r:SHOWS {asset: x.asset}]->(t) SET r.evidence = x.evidence, r.n = x.n, r.first = x.first, r.last = x.last",
    "UNWIND $te AS x MATCH (a:Address {key: x.from_key})-[s:SENT {asset: x.asset}]->(b:Address {key: x.to_key}) SET s.typologies = x.typologies",
    "UNWIND $in AS x MERGE (i:Instrument {id: x.id}) SET i.symbol = x.symbol, i.name = x.name, i.chain = x.chain, i.model = x.model, i.standard = x.standard, i.kind = x.kind, i.issuer = x.issuer, i.contract = x.contract, i.freeze = x.freeze, i.traceable = x.traceable, i.risk = x.risk, i.sanctioned = x.sanctioned_what, i.sanctioned_from = x.sanctioned_from, i.sanctioned_by = x.sanctioned_by, i.sanction_source = x.sanctioned_source, i.verify = coalesce(x.verify, false)",
    "UNWIND $in AS x UNWIND x.guidance AS gid MATCH (i:Instrument {id: x.id}) MATCH (g:Guidance {id: gid}) MERGE (i)-[:ADDRESSED_IN]->(g)",
]


def params(listed_keys, labels, categories):
    tt, tl, te, tg = detect(listed_keys, labels, categories)
    gd = json.load(open(os.path.join(HERE, 'data', 'crypto', 'guidance.json'), encoding='utf-8'))['guidance']
    gd = [{**{k: None for k in ('applies_from',)}, **g} for g in gd]
    ins = json.load(open(os.path.join(HERE, 'data', 'crypto', 'instruments.json'), encoding='utf-8'))['instruments']
    ins = [{**i, 'sanctioned_what': (i.get('sanctioned') or {}).get('what'), 'sanctioned_from': (i.get('sanctioned') or {}).get('from'),
            'sanctioned_by': (i.get('sanctioned') or {}).get('by'), 'sanctioned_source': (i.get('sanctioned') or {}).get('source'), 'verify': i.get('verify', False)}
           for i in ins]
    return {'tt': tt, 'tl': tl, 'te': te, 'tg': tg, 'gd': gd, 'in': [{k: v for k, v in i.items() if k != 'sanctioned'} for i in ins]}
