#!/usr/bin/env python3
"""Build the sector register: one Relate file with the classification of every sector in the Netherlands that is under AML
supervision or comes under it, its supervisor, the date it is obliged from, the duties of the sector with their passages, and the
office file of each (test) office. It holds no client data.

  Jurisdiction <-[:IN_JURISDICTION]- Sector <-[:SUPERVISES {role, aml}]- Regulator (AML supervisor, licensing authority, FIU-Nederland, AP)
  Sector -[:REQUIRES_LICENCE]-> Licence -[:GRANTED_BY]-> Regulator;  Sector -[:SUBJECT_TO]-> Law
  FatfScope (FI, VASP, DNFBP, other under the AMLR) <-[:IN_SCOPE]- Sector -[:IN_CATEGORY]-> SectorCategory (banking, payments, ...)
  Regulator -[:SUPERVISES]-> Sector -[:HAS_DUTY]-> SectorDuty -[:DEFINED_IN]-> Article -[:PART_OF]-> Law
  OfficeFile {file} -[:IN_SECTOR]-> Sector

usage:  python3 casefold/build_register.py          # -> register/sectors.rl
"""
import glob, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_case import find_relate, run, sector_duties, sector_class, CLASS_SCRIPT, HERE

SCRIPT = """
UNWIND $scopes AS f MERGE (x:FatfScope {id:f.id}) SET x.name=f.name, x.name_nl=f.name_nl;
UNWIND $cats AS c MERGE (x:SectorCategory {id:c.id}) SET x.name=c.name, x.name_nl=c.name_nl, x.order=c.order;
UNWIND $sectors AS s MERGE (x:Sector {id:s.id}) SET x.name=s.name, x.local=s.local, x.status=s.status, x.obliged_from=s.obliged_from, x.basis=s.basis,
    x.expected_supervisor=s.expected_supervisor, x.verify=s.verify
  WITH x, s MATCH (c:SectorCategory {id:s.category}), (f:FatfScope {id:s.fatf_scope}) MERGE (x)-[:IN_CATEGORY]->(c) MERGE (x)-[r:IN_SCOPE]->(f) SET r.source=s.fatf_source;
MERGE (j:Jurisdiction {code:'NL'}) SET j.name='Nederland';
UNWIND $sectors AS s MATCH (x:Sector {id:s.id}), (j:Jurisdiction {code:split(s.id, ':')[0]}) MERGE (x)-[:IN_JURISDICTION]->(j);
UNWIND $sups AS g MATCH (x:Sector {id:g.sector}) MERGE (r:Regulator {id:g.id}) SET r.short=g.short, r.name=g.name, r.basis=$auth[g.id].basis, r.basis_url=$auth[g.id].url, r.basis_verify=$auth[g.id].verify, r.basis_source=$auth[g.id].source MERGE (r)-[v:SUPERVISES]->(x) SET v.role=g.role, v.aml=g.aml;
UNWIND $lics AS l MATCH (s:Sector {id:l.sector}) MERGE (x:Licence {id:l.id}) SET x.kind=l.kind, x.name=l.name, x.basis=l.basis, x.url=l.url, x.verify=l.verify, x.note=l.note
  MERGE (s)-[:REQUIRES_LICENCE]->(x) WITH x, l MATCH (r:Regulator {id:l.authority}) MERGE (x)-[:GRANTED_BY]->(r);
UNWIND $slaws AS l MATCH (s:Sector {id:l.sector}) MERGE (x:Law {id:l.id}) SET x.short=l.short, x.title=l.title, x.url=l.url, x.kind=l.kind, x.valid_from=l.valid_from, x.scope=l.note
  MERGE (s)-[r:SUBJECT_TO]->(x) SET r.source=l.source;
UNWIND $laws AS l MERGE (x:Law {id:l.id}) SET x.short=l.short, x.title=l.title, x.url=l.url;
UNWIND $duties AS d MERGE (x:SectorDuty {id:d.id}) SET x.title=d.title, x.level=d.level, x.kind=d.kind, x.amount=d.amount, x.payment=d.payment,
  x.frequency=d.frequency, x.from_date=d.from_date, x.authority=d.authority, x.independent=d.independent, x.valid_from=d.valid_from, x.valid_to=d.valid_to, x.search=d.search;
UNWIND $duties AS d UNWIND range(0, size(d.basis) - 1) AS n WITH d, n, d.basis[n] AS b MATCH (x:SectorDuty {id:d.id}), (l:Law {id:b.law})
  MERGE (a:Article {id:'DUTY:' + d.id + ':' + toString(n)}) SET a.ref=b.ref, a.lang='nl', a.text_local=b.text, a.source_url=b.url, a.verify=b.verify, a.basis_kind=b.kind, a.text_en=coalesce(b.text_en, ''), a.en_type=coalesce(b.en_type, 'none'), a.valid_from=b.valid_from, a.valid_to=b.valid_to, a.regime=b.regime, a.law_short=b.law_short, a.art=b.art, a.lid=b.lid, a.heading=b.heading, a.read_in=b.read
  MERGE (x)-[:DEFINED_IN]->(a) MERGE (a)-[:PART_OF]->(l);
UNWIND $has AS h MATCH (s:Sector {id:h.sector}), (d:SectorDuty {id:h.duty}) MERGE (s)-[:HAS_DUTY]->(d);
UNWIND $duties AS d UNWIND [n IN range(0, size(d.basis) - 1) WHERE d.basis[n].replaces IS NOT NULL] AS n
  MATCH (o:Article {id:'DUTY:' + d.id + ':' + toString(d.basis[n].replaces)}), (a:Article {id:'DUTY:' + d.id + ':' + toString(n)}) MERGE (o)-[:REPLACED_BY]->(a);
UNWIND [d IN $duties WHERE d.replaces IS NOT NULL] AS d MATCH (o:SectorDuty {id:d.replaces}), (x:SectorDuty {id:d.id}) MERGE (o)-[:REPLACED_BY]->(x);
UNWIND $btypes AS b MERGE (t:BusinessType {code:b.code}) SET t.sbi=b.sbi, t.name=b.name, t.name_nl=b.name_nl
  WITH t, b UNWIND b.factors AS f MERGE (r:RiskFactor {id:f.id}) SET r.annex=f.annex, r.ref=f.ref, r.text=f.text MERGE (t)-[:HAS_RISK_FACTOR]->(r);
UNWIND $offices AS o MATCH (s:Sector {id:o.sector}) MERGE (x:OfficeFile {id:o.id}) SET x.name=o.name, x.file=o.file, x.test=o.test MERGE (x)-[:IN_SECTOR]->(s)
"""


def main():
    rel = find_relate(os.environ.get('RELATE_BIN'))
    BT = json.load(open(os.path.join(HERE, 'data', 'business_types.json'), encoding='utf-8'))
    btypes = [dict(code=k, sbi=v['sbi'], name=v['name'], name_nl=v['name_nl'], factors=[dict(id=f, **BT['factors'][f]) for f in v['factors']]) for k, v in BT['types'].items()]
    tax = json.load(open(os.path.join(HERE, 'data', 'sector_taxonomy.json'), encoding='utf-8'))
    sectors = json.load(open(os.path.join(HERE, 'data', 'sectors.json'), encoding='utf-8'))['sectors']
    for s in sectors:
        s.setdefault('status', 'supervised'); s.setdefault('obliged_from', None); s.setdefault('expected_supervisor', None)
    sups, lics, slaws = [], [], []
    for s in sectors:
        cls = sector_class(s['id'])
        sups += [{**g, 'sector': s['id']} for g in cls['supervisors']]
        if cls['licence']:
            lics.append({**cls['licence'], 'sector': s['id']})
        slaws += [{**l, 'sector': s['id']} for l in cls['laws']]
    duties, has, laws = {}, [], {}
    for s in sectors:
        ds, ls, _ = sector_duties(s)
        for d in ds:
            duties[d['id']] = d; has.append({'sector': s['id'], 'duty': d['id']})
        laws.update({l['id']: l for l in ls})
    laws.update({l['id']: l for l in [{'id': 'NL:wwft', 'short': 'Wwft', 'title': 'Wet ter voorkoming van witwassen en financieren van terrorisme', 'url': 'https://wetten.overheid.nl/BWBR0024282'},
                                      {'id': 'NL:wtt2018', 'short': 'Wtt 2018', 'title': 'Wet toezicht trustkantoren 2018', 'url': 'https://wetten.overheid.nl/BWBR0041259'},
                                      {'id': 'NL:uitvoeringsbesluit-wwft', 'short': 'Uitvoeringsbesluit Wwft 2018', 'title': 'Uitvoeringsbesluit Wwft 2018', 'url': 'https://wetten.overheid.nl/BWBR0041193'}]})
    offices = []
    for f in sorted(glob.glob(os.path.join(HERE, 'data', 'testcases', '*.json'))) + sorted(glob.glob(os.path.join(HERE, 'data', 'cases', '*.json'))):
        c = json.load(open(f, encoding='utf-8'))
        inst = c.get('institution_data') or next(i for i in json.load(open(os.path.join(HERE, 'data', 'institutions.json'), encoding='utf-8'))['institutions'] if i['id'] == c['institution'])
        test = 'testcases' in f
        offices.append({'id': inst['id'], 'name': inst['name'], 'sector': inst['sector']['id'], 'test': test,
                        'file': f"{'tests/offices' if test else 'offices'}/{inst['id']}.rl"})
    offices = list({o['id']: o for o in offices}.values())
    cats = [{**{k: c[k] for k in ('id', 'name', 'name_nl')}, 'order': i} for i, c in enumerate(tax['categories'])]
    os.makedirs(os.path.join(HERE, 'register'), exist_ok=True)
    db = os.path.join(HERE, 'register', 'sectors.rl')
    if os.path.exists(db):
        shutil.rmtree(db) if os.path.isdir(db) else os.remove(db)
    run(rel, db, {'scopes': tax['scopes'], 'cats': cats, 'sectors': sectors, 'laws': list(laws.values()), 'duties': list(duties.values()), 'has': has, 'offices': offices, 'sups': sups, 'lics': lics, 'slaws': slaws, 'btypes': btypes, 'auth': json.load(open(os.path.join(HERE, 'data', 'rules', 'authorities.json'), encoding='utf-8'))['authorities']}, script=SCRIPT)
    counts = run(rel, db, {}, command='MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY label', read=True)
    print(f"register/sectors.rl: " + ', '.join(f"{r['label']} {r['n']}" for r in counts))


if __name__ == '__main__':
    main()
