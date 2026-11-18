#!/usr/bin/env python3
"""Build one Relate file per office: the office itself and an overview of its client files.

Two levels, two kinds of file:
  - the client file (cases/<case>.rl, built by build_case.py) holds the client, its documents, its sub-clients (KYCC) and its
    transactions: client data stays there;
  - the office file (offices/<office>.rl) holds the office, its sector, its supervisor, the duties of the sector with their passages,
    the evidence of its own periodic duties (OfficeRecord), and one ClientFile node per client: the file name, the business type and
    risk band, and the signals that file gives on the date of the build (UBO answer, sector duties that need action, monitoring
    signals). Counterparties are present only as one-way keys (CounterpartyKey), so a counterparty that recurs across clients can be
    seen without its name. No names of clients, owners or sub-clients go into the office file.

usage:  python3 casefold/build_office.py                      # the demo office (data/cases) -> offices/
        python3 casefold/build_office.py --tests              # the 37 test offices (data/testcases, tests/cases) -> tests/offices/
"""
import argparse, glob, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_case import find_relate, run, sector_duties, sector_class, CLASS_SCRIPT, HERE
import clock

SCRIPT = """
MERGE (i:Institution {id:$i.id}) SET i.name=$i.name, i.fictitious=$i.fictitious, i.kind='office file'
MERGE (s:Sector {id:$i.sector.id}) SET s.name=$i.sector.name, s.local=$i.sector.local, s.status=$i.sector.status, s.obliged_from=$i.sector.obliged_from,
  s.cdd=$scope.cdd, s.cdd_until=$scope.cdd_until, s.cdd_from=$scope.cdd_from, s.only_duties=$scope.only_duties, s.scope_note=$scope.note
MERGE (i)-[:IN_SECTOR]->(s)
MERGE (g:Regulator {id:$i.regulator.id}) SET g.short=$i.regulator.short, g.name=$i.regulator.name MERGE (g)-[sv:SUPERVISES]->(s) SET sv.aml=true;
UNWIND $dlaws AS l MERGE (x:Law {id:l.id}) SET x.short=l.short, x.title=l.title, x.url=l.url;
UNWIND [['NL:wwft', 'Wwft', 'Wet ter voorkoming van witwassen en financieren van terrorisme', 'https://wetten.overheid.nl/BWBR0024282'],
        ['NL:wtt2018', 'Wtt 2018', 'Wet toezicht trustkantoren 2018', 'https://wetten.overheid.nl/BWBR0041259'],
        ['NL:uitvoeringsbesluit-wwft', 'Uitvoeringsbesluit Wwft 2018', 'Uitvoeringsbesluit Wwft 2018', 'https://wetten.overheid.nl/BWBR0041193']] AS l
  MERGE (x:Law {id:l[0]}) SET x.short=l[1], x.title=l[2], x.url=l[3];
UNWIND $duties AS d MATCH (s:Sector) MERGE (x:SectorDuty {id:d.id}) SET x.title=d.title, x.level=d.level, x.kind=d.kind, x.amount=d.amount, x.payment=d.payment, x.tx=d.tx,
  x.frequency=d.frequency, x.from_date=d.from_date, x.authority=d.authority, x.independent=d.independent, x.valid_from=d.valid_from, x.valid_to=d.valid_to MERGE (s)-[:HAS_DUTY]->(x);
UNWIND $duties AS d UNWIND range(0, size(d.basis) - 1) AS n WITH d, n, d.basis[n] AS b MATCH (x:SectorDuty {id:d.id}), (l:Law {id:b.law})
  MERGE (a:Article {id:'DUTY:' + d.id + ':' + toString(n)}) SET a.ref=b.ref, a.lang='nl', a.text_local=b.text, a.source_url=b.url, a.verify=b.verify, a.basis_kind=b.kind, a.read_in=b.read
  MERGE (x)-[:DEFINED_IN]->(a) MERGE (a)-[:PART_OF]->(l);
UNWIND coalesce($i.records, []) AS r MATCH (i:Institution {id:$i.id}) MERGE (x:OfficeRecord {id:r.id}) SET x.duty=r.duty, x.date=r.date, x.title=r.title MERGE (i)-[:HAS_RECORD]->(x)
  WITH x, r MATCH (d:SectorDuty {id:r.duty}) MERGE (x)-[:FULFILS]->(d);
UNWIND $clients AS c MATCH (i:Institution {id:$i.id}) MERGE (f:ClientFile {id:c.case}) SET f.case=c.case, f.file=c.file, f.legal_form=c.legal_form, f.service=c.service,
  f.ubo=c.ubo, f.actions=c.actions, f.monitoring=c.monitoring, f.as_of=c.as_of, f.business_type=c.business_type, f.sbi=c.sbi, f.risk_band=c.risk_band MERGE (f)-[:CLIENT_OF]->(i);
UNWIND $clients AS c UNWIND c.counterparty_keys AS k MATCH (f:ClientFile {id:c.case}) MERGE (x:CounterpartyKey {key:k}) MERGE (f)-[:HAS_COUNTERPARTY]->(x)
"""


def q(name, on):
    path = glob.glob(os.path.join(HERE, 'queries', name + '_*.cypher'))[0]
    return open(path, encoding='utf-8').read().strip().rstrip(';').replace('$on', "'" + on + "'")


def signals(rel, db, on):
    """What one client file says on `on`, without names: read with the case questions 03, 15, 16 and 17."""
    ubo = run(rel, db, {}, command=q('03', on), read=True)
    natural = run(rel, db, {}, read=True, command="MATCH (c:Client {natural_person:true}) RETURN c.id AS id")
    sc = run(rel, db, {}, read=True, command="MATCH (:Client)-[:CLIENT_OF]->(:Institution)-[:IN_SECTOR]->(s:Sector) RETURN s.cdd AS cdd, s.cdd_until AS u, s.cdd_from AS f")[0]
    no_cdd = sc['cdd'] is False or (sc['u'] and on > sc['u']) or (sc['f'] and on < sc['f'])
    n_ubo = sum(1 for r in ubo if r['ubo'])
    undeclared = sum(1 for r in ubo if r['ubo'] and r.get('declaration') != 'declared')
    if no_cdd:
        u = 'no CDD in this sector'
    elif natural:
        u = 'natural person'
    elif n_ubo:
        u = f"{n_ubo} UBO(s)" + (f", {undeclared} not declared" if undeclared else '')
    else:
        fb = run(rel, db, {}, command=q('15', on), read=True)
        u = f"nobody qualifies: {len(fb)} senior managing official(s)" if fb else 'no UBO rule for this date'
    duties = run(rel, db, {}, command=q('16', on), read=True)
    actions = sorted({'REPORT sanctions hit' if r['status'].startswith('REPORT hit') else r['status'].split(':')[0] for r in duties
                      if r['status'].split(':')[0] in ('VIOLATION', 'REPORT to FIU-NL', 'CDD required', 'FREEZE', 'EDD required', 'ASK for the customs declaration') or r['status'].startswith('REPORT hit')})
    mon = sorted({r['check'] for r in run(rel, db, {}, command=q('17', on), read=True) if r['status'].startswith('FLAG')})
    keys = sorted({r['key'] for r in run(rel, db, {}, read=True, command="MATCH (k:Counterparty) WHERE k.key IS NOT NULL RETURN k.key AS key")})
    bt = run(rel, db, {}, read=True, command="MATCH (c:Client) OPTIONAL MATCH (c)-[:HAS_BUSINESS_TYPE]->(t:BusinessType) RETURN t.code AS code, t.sbi AS sbi, c.risk_band AS band")
    return u, actions, mon, keys, (bt[0] if bt else {})


def build_office(rel, inst, clients, out_dir, on):
    os.makedirs(out_dir, exist_ok=True)
    db = os.path.join(out_dir, inst['id'] + '.rl')
    if os.path.exists(db):
        shutil.rmtree(db) if os.path.isdir(db) else os.remove(db)
    duties, dlaws, scope = sector_duties(inst['sector'])
    duties = [d for d in duties if d['level'] == 'office']     # the office file holds the office's own duties; the KYC duties per client are in the client files
    inst = {**inst, 'sector': {'status': 'supervised', 'obliged_from': None, **inst['sector']}}
    run(rel, db, {'i': inst, 'duties': duties, 'dlaws': dlaws, 'scope': scope, 'clients': clients}, script=SCRIPT)
    run(rel, db, {'cls': sector_class(inst['sector']['id'])}, script=CLASS_SCRIPT)
    return db


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tests', action='store_true', help='build the test offices from data/testcases and tests/cases')
    ap.add_argument('--on', default=clock.today().isoformat())
    a = ap.parse_args()
    rel = find_relate(os.environ.get('RELATE_BIN'))
    src, cases_dir, out = (('testcases', 'tests/cases', 'tests/offices') if a.tests else ('cases', 'cases', 'offices'))
    insts = {i['id']: i for i in json.load(open(os.path.join(HERE, 'data', 'institutions.json'), encoding='utf-8'))['institutions']}
    offices = {}
    for f in sorted(glob.glob(os.path.join(HERE, 'data', src, '*.json'))):
        case = json.load(open(f, encoding='utf-8'))
        inst = case.get('institution_data') or insts[case['institution']]
        db = os.path.join(HERE, cases_dir, case['id'] + '.rl')
        if not os.path.exists(db):
            sys.exit(f'{db} not built yet: run build_case.py first')
        u, actions, mon, keys, bt = signals(rel, db, a.on)
        offices.setdefault(inst['id'], (inst, []))[1].append({'case': case['id'], 'file': os.path.relpath(db, HERE), 'legal_form': case['client'].get('legal_form'),
            'service': (case['client'].get('service_profile') or {}).get('name'), 'ubo': u, 'actions': actions, 'monitoring': mon, 'as_of': a.on,
            'counterparty_keys': keys, 'business_type': bt.get('code'), 'sbi': bt.get('sbi'), 'risk_band': bt.get('band')})
    for inst, clients in offices.values():
        db = build_office(rel, inst, clients, os.path.join(HERE, out), a.on)
        print(f"{os.path.relpath(db, HERE)}: {inst['name']}, {len(clients)} client file(s), {sum(len(c['actions']) + len(c['monitoring']) for c in clients)} signals (as of {a.on})")


if __name__ == '__main__':
    main()
