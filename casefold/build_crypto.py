"""Casefold Crypto Intelligence: build the crypto register (register/crypto.rl) and the viewer data (web/data/crypto.json).

Wave 1 is the Netherlands, with the same ids as the Casefold sector register (NL:afm, NL:dnb, NL:mica, NL:wwft, ...);
wave 2 the EU, wave 3 the rest of the world. Every case links to the decision or press release it comes from.

  (:Regulator)-[:SUPERVISES {role, aml}]->(:Sector)-[:IN_JURISDICTION]->(:Jurisdiction)
  (:Sector)-[:SUBJECT_TO]->(:Law)
  (:Source {kind:'case'})-[:BY]->(:Regulator), -[:AGAINST]->(:Entity), -[:VIOLATED {art}]->(:Law), -[:IN_JURISDICTION]->(:Jurisdiction)
  (:SanctionsList)-[:PUBLISHED_BY]->(:Regulator)    later: (:SanctionsList)-[:LISTS]->(:Entity|:Address)

The same statements build the graph here with the Relate CLI and in the browser with Relate in WebAssembly (web/crypto.html),
so the page and the file cannot drift apart.

  python3 casefold/build_crypto.py            build register/crypto.rl (needs relate) and web/data/crypto.json
  python3 casefold/build_crypto.py --export   only web/data/crypto.json (no relate needed)
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, 'casefold'))

LOAD = [
    # jurisdictions and the crypto sector in each
    """UNWIND $j AS j
MERGE (x:Jurisdiction {code: j.code}) SET x.name = j.name, x.wave = j.wave, x.regime = j.regime, x.travel_rule = j.travel_rule, x.verify = j.verify
MERGE (s:Sector {id: j.sector}) SET s.name = 'crypto-asset service providers', s.group = 'crypto'
MERGE (s)-[:IN_JURISDICTION]->(x)""",
    # supervisors and their role
    """UNWIND $j AS j UNWIND j.regulators AS r
MATCH (s:Sector {id: j.sector})
MERGE (g:Regulator {id: r.id}) SET g.short = r.short, g.name = r.name, g.url = r.url
MERGE (g)-[v:SUPERVISES]->(s) SET v.role = r.role, v.aml = r.aml""",
    # laws the sector is subject to
    """UNWIND $j AS j UNWIND j.laws AS l
MATCH (s:Sector {id: j.sector})
MERGE (w:Law {id: l.id}) SET w.short = l.short, w.title = l.title, w.url = l.url
MERGE (s)-[:SUBJECT_TO]->(w)""",
    # public enforcement cases
    """UNWIND $c AS c
MERGE (k:Source {id: c.id}) SET k.kind = 'case', k.title = c.title, k.party = c.party, k.date = c.date, k.measure = c.measure,
  k.amount = CASE WHEN c.amount IS NULL THEN null ELSE toFloat(c.amount) END, k.currency = c.currency, k.amount_note = c.amount_note,
  k.summary = c.summary, k.chain = c.chain, k.url = c.url, k.verify = c.verify,
  k.published = c.published, k.status = c.status, k.period = c.period, k.decision = c.decision, k.note = c.note, k.violated_from = c.violated_from
MERGE (e:Entity {id: 'ENTITY:' + coalesce(c.group, toLower(c.party))}) SET e.name = coalesce(e.name, c.party), e.group = c.group
MERGE (k)-[:AGAINST]->(e)
WITH k, c MATCH (x:Jurisdiction {code: c.jurisdiction}) MERGE (k)-[:IN_JURISDICTION]->(x)""",
    """UNWIND $c AS c UNWIND c.authorities AS a
MATCH (k:Source {id: c.id})
MATCH (x:Jurisdiction {code: c.jurisdiction})<-[:IN_JURISDICTION]-(:Sector)<-[:SUPERVISES]-(g:Regulator {short: a})
MERGE (k)-[:BY]->(g)""",
    """UNWIND $c AS c UNWIND c.violated AS v
MATCH (k:Source {id: c.id}) MATCH (w:Law {id: v.law})
MERGE (k)-[r:VIOLATED {art: coalesce(v.art, '')}]->(w) SET r.lids = coalesce(v.lids, []), r.stated = coalesce(v.stated, false)""",
    # the article that gives the authority its power (art. 30 Wwft for a fine, art. 29 for a last onder dwangsom)
    """UNWIND [c IN $c WHERE c.power IS NOT NULL] AS c
MATCH (k:Source {id: c.id}) MATCH (w:Law {id: c.power.law})
MERGE (k)-[r:UNDER_POWER {art: c.power.art}]->(w) SET r.point = c.power.point""",
    # key articles with their text from the law files, the cases that violated them, and what replaced them
    """UNWIND $a AS a
MATCH (w:Law {id: a.law})
MERGE (x:Article {id: a.law + ':' + a.art}) SET x.law = a.law, x.law_short = w.short, x.art = a.art, x.heading = a.heading, x.duty = a.duty,
  x.text = a.text, x.status = a.status, x.version = a.version, x.source_sha256 = a.sha256
MERGE (w)-[:HAS_ARTICLE]->(x)""",
    """UNWIND $a AS a UNWIND a.replaced_by AS r
MATCH (x:Article {id: a.law + ':' + a.art}) MATCH (y:Article {id: r})
MERGE (x)-[:REPLACED_BY]->(y)""",
    """UNWIND $c AS c UNWIND c.violated AS v
MATCH (k:Source {id: c.id}) MATCH (x:Article {id: v.law + ':' + coalesce(v.art, '')})
MERGE (k)-[r:VIOLATED_ARTICLE]->(x) SET r.lids = coalesce(v.lids, []), r.stated = coalesce(v.stated, false)""",
    # sanctions lists, with what the daily import found
    """UNWIND $l AS l
MERGE (x:SanctionsList {id: l.id}) SET x.name = l.name, x.url = l.url, x.refresh = l.refresh, x.imported = coalesce(l.imported, false),
  x.entries_total = l.entries_total, x.addresses_total = l.addresses_total, x.fetched = l.fetched, x.sha256 = l.sha256
WITH x, l OPTIONAL MATCH (g:Regulator {id: l.owner}) FOREACH (_ IN CASE WHEN g IS NULL THEN [] ELSE [1] END | MERGE (x)-[:PUBLISHED_BY]->(g))""",
    # listed persons and entities that have crypto addresses on a list, and those addresses
    """UNWIND $s AS e
MATCH (l:SanctionsList {id: e.list})
MERGE (x:Entity {id: e.id}) SET x.name = e.name, x.type = e.type, x.programs = e.programs, x.aliases = e.aliases, x.listed = true
MERGE (l)-[:LISTS]->(x)
WITH x, l, e UNWIND e.addresses AS a
MERGE (y:Address {key: a.chain + ':' + a.address}) SET y.chain = a.chain, y.address = a.address, y.currency = a.currency, y.unlabelled = coalesce(a.unlabelled, false)
MERGE (x)-[:CONTROLS]->(y)
MERGE (l)-[:LISTS]->(y)""",
    # a party in a case whose name matches a listed entity: a lead to check, not a finding
    """UNWIND $m AS m
MATCH (a:Entity {id: m.case_entity}) MATCH (b:Entity {id: m.listed})
MERGE (a)-[r:POSSIBLY_SAME]->(b) SET r.by = m.by""",
]


def data():
    d = os.path.join(HERE, 'data', 'crypto')
    j = json.load(open(os.path.join(d, 'jurisdictions.json'), encoding='utf-8'))['jurisdictions']
    c = json.load(open(os.path.join(d, 'cases.json'), encoding='utf-8'))
    l = json.load(open(os.path.join(d, 'sanctions_lists.json'), encoding='utf-8'))['lists']
    return j, c, l


def articles():
    """The key articles, each with its text from the newest Dutch law file under laws/ (where it is read in)."""
    out, laws = [], {}
    for f in sorted(os.listdir(os.path.join(HERE, 'laws'))):
        if f.endswith('-nl.json'):
            v = json.load(open(os.path.join(HERE, 'laws', f), encoding='utf-8'))
            if v.get('law') and (v['law'] not in laws or v['version'] > laws[v['law']]['version']):
                laws[v['law']] = v
    for a in json.load(open(os.path.join(HERE, 'data', 'crypto', 'articles.json'), encoding='utf-8'))['articles']:
        v = laws.get(a['law']); t = None
        if v:
            t = next((x['text'] for x in v['article_list'] if x['number'] == a['art']), None)
        status = 'vervallen' if (t or '').strip().lower().startswith('vervallen') else ('in force' if t else 'text not read in')
        out.append({**a, 'text': (t or '')[:1500] if status == 'in force' else None, 'status': status,
                    'version': v['version'] if v else None, 'sha256': v.get('sha256') if v else None})
    return out


def check(j, c, l):
    """Every case has a date, a source URL and a known jurisdiction; every violated law exists; ids are unique."""
    errors, laws, codes = [], {w['id'] for x in j for w in x['laws']}, {x['code'] for x in j}
    shorts = {x['code']: {r['short'] for r in x['regulators']} for x in j}
    for k in c['cases']:
        if not re.match(r'^https://', k.get('url') or ''): errors.append(f"{k['id']}: no https source")
        if not re.match(r'^\d{4}(-\d{2})?(-\d{2})?$', k.get('date') or ''): errors.append(f"{k['id']}: bad date {k.get('date')}")
        if k['jurisdiction'] not in codes: errors.append(f"{k['id']}: unknown jurisdiction {k['jurisdiction']}")
        for v in k['violated']:
            if v['law'] not in laws: errors.append(f"{k['id']}: unknown law {v['law']}")
        for a in k['authorities']:
            if a not in shorts.get(k['jurisdiction'], set()) and a not in ('USSS',): errors.append(f"{k['id']}: authority {a} not a supervisor in {k['jurisdiction']}")
    for name, ids in (('case', [k['id'] for k in c['cases']]), ('jurisdiction', [x['code'] for x in j]), ('list', [x['id'] for x in l])):
        dup = {i for i in ids if ids.count(i) > 1}
        if dup: errors.append(f'duplicate {name} ids: {sorted(dup)}')
    regs = {}
    for x in j:
        for r in x['regulators']:
            if regs.setdefault(r['id'], r['short']) != r['short']: errors.append(f"regulator {r['id']}: two shorts")
    return errors


def sanctions(l):
    """Per list what the import found; the listed entries that carry crypto addresses; name matches with case parties."""
    d = os.path.join(HERE, 'data', 'crypto', 'sanctions')
    ents, lists = [], []
    for x in l:
        f = os.path.join(d, x['id'].split(':', 1)[1] + '.json')
        if os.path.exists(f):
            r = json.load(open(f, encoding='utf-8'))
            x = {**x, 'imported': True, 'entries_total': r['entries_total'], 'addresses_total': r['addresses_total'], 'fetched': r['fetched'], 'sha256': r['sha256']}
            ents += [{**e, 'list': x['id']} for e in r['entries'] if e['addresses']]
        lists.append(x)
    return lists, ents


def name_matches(cases, ents):
    """A case party whose distinctive name (6+ letters, not a legal form) appears in a listed entity's name or alias."""
    stop = {'limited', 'holdings', 'global', 'international', 'markets', 'fintech', 'payments', 'services', 'cryptohandel', 'stichting', 'unnamed', 'provider', 'service', 'crypto', 'europe', 'europa', 'netherlands', 'nederland', 'exchange', 'trading', 'company', 'technologies'}
    out = []
    for c in cases:
        cid = 'ENTITY:' + (c.get('group') or c['party'].lower())
        words = {w for w in re.findall(r'[a-z]{6,}', c['party'].lower()) if w not in stop}
        for e in ents:
            names = ' '.join([e['name']] + e.get('aliases', [])).lower()
            hit = next((w for w in sorted(words) if re.search(r'\b' + w + r'\b', names)), None)
            if hit:
                out.append({'case_entity': cid, 'listed': e['id'], 'by': f'name: {hit}'})
    return sorted((dict(t) for t in {tuple(sorted(x.items())) for x in out}), key=lambda x: (x['case_entity'], x['listed']))


def names_index(l):
    """Every listed name and alias, for name screening in the viewer: [id, name, aliases, list, type]."""
    d = os.path.join(HERE, 'data', 'crypto', 'sanctions'); rows = []
    for x in l:
        f = os.path.join(d, x['id'].split(':', 1)[1] + '.json')
        if os.path.exists(f):
            for e in json.load(open(f, encoding='utf-8'))['entries']:
                rows.append([e['id'], e['name'], ' | '.join(e.get('aliases', [])), x['id'], e.get('type', '')])
    return rows


def queries():
    qd = os.path.join(HERE, 'queries', 'crypto')
    return {f[:-7]: open(os.path.join(qd, f), encoding='utf-8').read() for f in sorted(os.listdir(qd)) if f.endswith('.cypher')}


def export(j, c, l):
    out = os.path.join(HERE, 'web', 'data', 'crypto.json')
    l, ents = sanctions(l)
    json.dump(names_index(l), open(os.path.join(HERE, 'web', 'data', 'sanctions_names.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    schema = [s.strip() for s in open(os.path.join(HERE, 'schema', 'crypto.cypher'), encoding='utf-8').read().split(';')]
    schema = [re.sub(r'(?m)^//.*\n?', '', s).strip() for s in schema]
    json.dump({'as_of': c.get('as_of'), 'schema': [s for s in schema if s], 'load': LOAD, 'params': {'j': j, 'c': c['cases'], 'l': l, 'a': articles(), 's': ents, 'm': name_matches(c['cases'], ents)},
               'queue': c.get('queue', []), 'queries': queries()}, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return out


def main():
    j, c, l = data()
    errors = check(j, c, l)
    if errors:
        sys.exit('crypto data:\n  ' + '\n  '.join(errors))
    out = export(j, c, l)
    print(f'crypto: {len(j)} jurisdictions, {len(c["cases"])} cases, {len(l)} sanctions lists -> {os.path.relpath(out, HERE)}')
    if '--export' in sys.argv:
        return
    from build_case import find_relate, run
    rel = find_relate(os.environ.get('RELATE_BIN'))
    db = os.path.join(HERE, 'register', 'crypto.rl')
    if os.path.exists(db):
        os.remove(db)
    run(rel, db, {}, script=open(os.path.join(HERE, 'schema', 'crypto.cypher'), encoding='utf-8').read())
    ls, ents = sanctions(l)
    run(rel, db, {'j': j, 'c': c['cases'], 'l': ls, 'a': articles(), 's': ents, 'm': name_matches(c['cases'], ents)}, script=';\n'.join(LOAD) + ';')
    print(f'crypto: {os.path.relpath(db, HERE)}')


if __name__ == '__main__':
    main()
