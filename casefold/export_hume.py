"""Export the crypto register as a graph for the Hume workspace (knode-platform, gatekeeper/hume).

Same data as web/data/crypto.json, in the shape the Hume workspace reads from /fci-api
(nodes: {id, labels, source, properties}; relationships: {start_id, end_id, type, properties}),
and with the labels it already knows how to draw:

    sanctions list        -> SanctionAuthority         listed party  -> Organization | Person (source SCREENING)
    listing               -> ScreeningHit              crypto address -> Wallet (source BLOCKCHAIN)
    transfer on chain     -> Transaction  (Wallet -SENT-> Transaction -RECEIVED-> Wallet)
    supervisor            -> Organization (source 3RD) country        -> Jurisdiction (with lat/lon)
    enforcement case      -> Document (kind case)      article        -> Document (kind article)

    python3 casefold/export_hume.py            # -> exports/hume/casefold-crypto.json
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'exports', 'hume', 'casefold-crypto.json')

# Approximate centre (capital) per jurisdiction, for the geospatial view only.
LATLON = {'NL': (52.37, 4.90), 'EU': (50.85, 4.35), 'DE': (50.11, 8.68), 'FR': (48.86, 2.35), 'GB': (51.51, -0.13),
          'US': (38.90, -77.04), 'CH': (46.95, 7.45), 'SG': (1.29, 103.85), 'HK': (22.32, 114.17), 'JP': (35.68, 139.69),
          'KR': (37.57, 126.98), 'AE': (24.45, 54.38), 'AU': (-35.28, 149.13), 'CA': (45.42, -75.70), 'BR': (-15.79, -47.88),
          'ZA': (-25.75, 28.19), 'CW': (12.11, -68.93), 'INT': (48.85, 2.29)}
SEVERITY = {'severe': 'High', 'high': 'High', 'medium': 'Medium', 'low': 'Low', 'none': 'Low'}


def build():
    p = json.load(open(os.path.join(ROOT, 'web', 'data', 'crypto.json')))['params']
    nodes, rels = {}, []

    def node(i, label, source, **props):
        props = {k: v for k, v in props.items() if v not in (None, '', [])}
        props.setdefault('display', props.get('name') or props.get('title') or props.get('address') or i)
        if i not in nodes:
            nodes[i] = {'id': i, 'labels': [label], 'source': source, 'properties': props}
        return i

    def rel(a, t, b, **props):
        rels.append({'start_id': a, 'end_id': b, 'type': t, 'properties': {k: v for k, v in props.items() if v not in (None, '')}})

    for j in p['j']:
        lat, lon = LATLON.get(j['code'], (None, None))
        node('JUR-' + j['code'], 'Jurisdiction', '3RD', name=j['name'], isoCode=j['code'], regime=j.get('regime'),
             travelRule=j.get('travel_rule'), wave=j.get('wave'), lat=lat, lon=lon, toVerify=j.get('verify') or None)
        for r in j.get('regulators') or []:
            node('REG-' + r['id'], 'Organization', '3RD', name=r.get('short') or r['name'], fullName=r['name'],
                 orgType='Supervisor', jurisdiction=j['name'], role=r.get('role'), url=r.get('url'))
            rel('REG-' + r['id'], 'SUPERVISES_IN', 'JUR-' + j['code'], role=r.get('role'), aml=r.get('aml'))
    short = {r['short']: 'REG-' + r['id'] for j in p['j'] for r in j.get('regulators') or [] if r.get('short')}

    cats = {c['id']: c for c in p['rc']}
    ent_cat = {}
    for e in p['ec']:
        ent_cat.setdefault(e['entity'], []).append(e['category'])

    for l in p['l']:
        if not l.get('imported'):
            continue
        node('LIST-' + l['id'], 'SanctionAuthority', 'SCREENING', name=l['name'], url=l.get('url'), fetched=l.get('fetched'),
             entries=l.get('entries_total'), addresses=l.get('addresses_total'), sha256=l.get('sha256'), refresh=l.get('refresh'))

    lid = {'OFAC': 'LIST:ofac-sdn', 'EU': 'LIST:eu-fsf', 'UN': 'LIST:un-sc', 'UK': 'LIST:uk'}
    for s in p['s']:
        cs = ent_cat.get(s['id'], [])
        worst = min((cats[c]['severity'] for c in cs if c in cats), key=['severe', 'high', 'medium', 'low', 'none'].index, default=None)
        label = 'Person' if s.get('type') == 'individual' else 'Organization'
        eid = node('ENT-' + s['id'], label, 'SCREENING', name=s['name'], orgType='Listed on a sanctions list' if label == 'Organization' else None,
                   aliases=(s.get('aliases') or [])[:6], programmes=s.get('programs'), riskCategories=[cats[c]['name'] for c in cs if c in cats],
                   riskRating=SEVERITY.get(worst))
        list_id = lid.get(s['id'].split(':')[0])
        if list_id and 'LIST-' + list_id in nodes:
            hit = node('HIT-' + s['id'], 'ScreeningHit', 'SCREENING', listName=nodes['LIST-' + list_id]['properties']['name'],
                       matchType='Sanctions', matchScore=1.0, status='Listed', checkedAt=(nodes['LIST-' + list_id]['properties'].get('fetched') or '')[:10],
                       entryId=s['id'], display=f"{s['id'].split(':')[0]} listing {s['id'].split(':')[1]}")
            rel(eid, 'SCREENED_AGAINST', hit)
            rel(hit, 'LISTED_BY', 'LIST-' + list_id)
        for a in s.get('addresses') or []:
            wid = node('W-' + a['chain'] + ':' + a['address'], 'Wallet', 'BLOCKCHAIN', address=a['address'], chain=a['chain'],
                       currency=a.get('currency'), listed=True, display=a['address'][:8] + '…' + a['address'][-6:])
            rel(wid, 'CONTROLLED_BY', eid)

    labels = {x['key']: x for x in p['al']}
    for t in p['t']:
        for k in (t['from_key'], t['to_key']):
            chain, addr = k.split(':', 1)
            lab = labels.get(k)
            node('W-' + k, 'Wallet', 'BLOCKCHAIN', address=addr, chain=chain, cluster=lab['label'] if lab else None,
                 labelSource=lab['source'] if lab else None, category=cats[lab['category']]['name'] if lab and lab.get('category') in cats else None,
                 display=lab['label'] if lab else addr[:8] + '…' + addr[-6:])
        tid = node(f"TX-{t['chain']}-{t.get('tx') or ''}-{t['from'][:10]}-{t['to'][:10]}-{t['asset']}", 'Transaction', 'BLOCKCHAIN',
                   txnId=t.get('tx'), amount=t['amount'], currency=t['asset'], date=t.get('last') or t.get('first'), firstDate=t.get('first'),
                   transfers=t.get('count'), hop=t.get('hop'), chain=t['chain'], display=f"{t['amount']:,.4g} {t['asset']}")
        rel('W-' + t['from_key'], 'SENT', tid)
        rel(tid, 'RECEIVED', 'W-' + t['to_key'])

    arts = {}
    for a in p['a']:
        aid = node(f"ART-{a['law']}:{a['art']}", 'Document', 'KYC', kind='article', title=f"{a['law'].split(':')[-1].upper()} art. {a['art']}",
                   text=a.get('duty'), status=a.get('status'), version=a.get('version'), sha256=a.get('sha256'))
        arts[(a['law'], a['art'])] = aid

    for c in p['c']:
        cid = node('CASE-' + c['id'], 'Document', 'KYC', kind='enforcement case', title=c['title'], created=c['date'], url=c.get('decision') or c.get('url'),
                   text=c.get('summary'), measure=c['measure'], amount=None if c.get('amount_note') else c.get('amount'), currency=c.get('currency'),
                   amountNote=c.get('amount_note'), status=c.get('status'), toVerify=c.get('verify') or None)
        party = 'PARTY-' + (c.get('group') or c['party'].lower())
        node(party, 'Organization', 'KYC', name=c['party'], orgType='Party in an enforcement case')
        rel(cid, 'AGAINST', party)
        rel(cid, 'IN_JURISDICTION', 'JUR-' + c['jurisdiction'])
        for a in c.get('authorities') or []:
            if a in short:
                rel(short[a], 'ISSUED', cid, date=c['date'])
        for v in c.get('violated') or []:
            if (v['law'], v['art']) in arts:
                rel(cid, 'VIOLATED', arts[(v['law'], v['art'])], paragraphs=','.join(v.get('lids') or []), statedInDecision=v.get('stated'))
    for m in p['m']:
        a, b = 'PARTY-' + m['case_entity'].split(':', 1)[1], 'ENT-' + m['listed']
        if a in nodes and b in nodes:
            rel(a, 'POSSIBLY_SAME', b, matchedBy=m['by'])

    rels = [r for r in rels if r['start_id'] in nodes and r['end_id'] in nodes]
    return {'_about': 'Casefold Crypto Intelligence: public sanctions lists, explorer traces, regulators and enforcement cases. '
                      'Real public data; a list match or an explorer label is a lead, not a finding.',
            'nodes': list(nodes.values()), 'relationships': rels}


def main():
    g = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as f:
        json.dump(g, f, ensure_ascii=False, separators=(',', ':'))
    from collections import Counter
    print(f"hume: {len(g['nodes'])} nodes, {len(g['relationships'])} relationships -> {os.path.relpath(OUT, ROOT)}")
    print(dict(Counter(n['labels'][0] for n in g['nodes'])))


if __name__ == '__main__':
    main()
