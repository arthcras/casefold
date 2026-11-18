#!/usr/bin/env python3
"""Start a client file from the client's own documents, then review it.

A folder per client:
    <folder>/client.json     the client in a few lines: name, legal form, jurisdiction, risk, the office (see examples/)
    <folder>/documents/      what the client delivered, named after the document type:
                             structure_chart.pdf, ubo_register_extract.png, ubo_declaration.pdf, person_id.jpg, ...
                             (the types are listed by --types; any other name is stored as type "other")

What happens, all on this machine (no AI, no web service):
  1. build      cases/<id>.rl: the client, the slice of law and the sector duties that apply, and which document types are required
  2. read       every document becomes Chunks in the graph: text or OCR (Tesseract) with page and position
  3. structure  the structure chart becomes proposals (parties, OWNS, CONTROLS, BOARD_OF), each STATED_IN a chunk of the chart
  4. confirm    only with --confirm: the compliance officer accepts the proposals; then they are written as the client's structure
  5. review     required documents against the documents present (with the article behind each), and once the structure is
                confirmed: the beneficial owners against the UBO declaration and the UBO register extract

usage:  python3 casefold/new_client.py examples/kalmora-from-documents                 # build, read, propose, review
        python3 casefold/structure_chart.py cases/nl-kalmora-docs.rl --confirm all     # the officer confirms (or per id)
        python3 casefold/new_client.py examples/kalmora-from-documents --review        # review again, nothing rebuilt
        python3 casefold/new_client.py examples/kalmora-from-documents --confirm all   # build and confirm in one go
"""
import argparse, json, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_case import find_relate, build, EXTRA_DOCTYPES, HERE
from structure_chart import relate_q, propose, confirm, listing
import clock

REQUIRED = """
MATCH (c:Client)-[q:REQUIRES]->(t:DocumentType)
OPTIONAL MATCH (d:Document)-[:OF_TYPE]->(t)
OPTIONAL MATCH (c)-[:SUBJECT_TO]->(o:Obligation)-[:PROVEN_BY]->(t)
OPTIONAL MATCH (a:Article)-[:IMPOSES]->(o)
OPTIONAL MATCH (c)-[:HAS_TRIGGER]->(g:RiskTrigger)-[:ADDS_REQUIREMENT]->(t)
OPTIONAL MATCH (c)-[:HAS_LEGAL_FORM]->(f:LegalForm)-[:REQUIRES_DOC]->(t)
RETURN t.name AS type, collect(DISTINCT d.id + ' ' + d.title) AS present, collect(DISTINCT a.ref) AS articles,
       collect(DISTINCT g.name) AS triggers, collect(DISTINCT f.abbr) AS legal_form
ORDER BY size(present) > 0, type
"""


def doctypes():
    keys = {d['key'] for d in json.load(open(os.path.join(HERE, 'data', 'rulebook', 'NL.json'), encoding='utf-8'))['doctypes']}
    return sorted(keys | set(EXTRA_DOCTYPES))


def review(relate, db, on):
    print(f'\nREVIEW of {os.path.basename(db)} on {on}')
    rows = relate_q(relate, db, REQUIRED)
    print('\n  Required documents')
    for r in rows:
        basis = '; '.join(r['articles'] + [f"legal form {x}" for x in r['legal_form'] if x] + [f"risk: {x}" for x in r['triggers']]) or 'rule of the office'
        state = ('present: ' + ', '.join(r['present'])) if r['present'] else 'MISSING'
        print(f"   {'✓' if r['present'] else '✗'} {r['type'][:60]}\n       {state}\n       basis: {basis[:150]}")
    missing = [r for r in rows if not r['present']]
    pend = relate_q(relate, db, "MATCH (p:Proposal) RETURN p.status AS s, count(*) AS n")
    pend = {r['s']: r['n'] for r in pend}
    owners = relate_q(relate, db, 'MATCH ()-[r:OWNS|CONTROLS|BOARD_OF]->() RETURN count(r) AS n')[0]['n']
    print('\n  Beneficial owners')
    if not owners:
        print(f"   not determined: the structure is not confirmed yet ({pend.get('proposed', 0)} proposals from the structure chart wait for the compliance officer)")
        ubos = []
    else:
        q = open(os.path.join(HERE, 'queries', '03_beneficial_owners.cypher'), encoding='utf-8').read()
        ubos = relate_q(relate, db, '\n'.join(l for l in q.splitlines() if not l.startswith('//')), {'on': on})
        for u in ubos:
            flag = 'UBO' if u['ubo'] else '   '
            print(f"   {flag}  {u['person']:<18} shares {u['ownership']:>5}%  votes {u['votes']:>5}%  control {'yes' if u['control_other_means'] else 'no ':<3}  "
                  f"{', '.join(u['grounds_met']) or '-':<55} {u['declaration']}")
        if pend.get('proposed'):
            print(f"   ({pend['proposed']} proposals from the structure chart are still unconfirmed)")
    gaps = [u['person'] for u in ubos if u['ubo'] and u['declaration'] != 'declared']
    print('\n  Request to the client')
    for r in missing:
        print(f"   - {r['type']}" + (f" ({'; '.join(r['articles'][:2])})" if r['articles'] else ''))
    for p in gaps:
        print(f"   - explain why {p} is not in the UBO declaration / UBO register although the structure chart makes {p} a beneficial owner")
    print(f"\n  {len(rows) - len(missing)} of {len(rows)} required document types present, {len(missing)} missing; "
          f"{len([u for u in ubos if u['ubo']])} beneficial owners, {len(gaps)} not declared. The decision stays with the compliance officer.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder', nargs='?'); ap.add_argument('--confirm', nargs='+', metavar='ID')
    ap.add_argument('--review', action='store_true', help='review the existing file again; rebuild nothing')
    ap.add_argument('--on', default=clock.today().isoformat()); ap.add_argument('--types', action='store_true')
    ap.add_argument('--out', default=os.path.join(HERE, 'cases')); ap.add_argument('--relate')
    ap.add_argument('--template', metavar='ID', help='build only the client, without documents and structure, under this id: the starting point of '
                    '"New client from documents" in the viewer')
    a = ap.parse_args()
    if a.types:
        print('\n'.join(doctypes())); return
    if not a.folder:
        ap.error('give the client folder')
    relate = find_relate(a.relate)
    spec = json.load(open(os.path.join(a.folder, 'client.json'), encoding='utf-8'))
    if a.template:
        spec['id'] = a.template
    db = os.path.join(a.out, spec['id'] + '.rl')
    if not a.review:
        known = set(doctypes())
        files = [] if a.template else sorted(f for f in os.listdir(os.path.join(a.folder, 'documents')) if not f.startswith('.'))
        meta = spec.get('documents', {})
        docs = []
        for i, f in enumerate(files, 1):
            stem = re.sub(r'[-_ ]?\d+$', '', os.path.splitext(f)[0]).lower()
            docs.append({'id': f'D{i}', 'file': f, 'doctype': stem if stem in known else 'other',
                         'title': meta.get(f, {}).get('title') or stem.replace('_', ' ').capitalize(), 'date': meta.get(f, {}).get('date')})
        case = {k: v for k, v in spec.items() if k != 'documents'}
        case.update({'documents': [{k: d[k] for k in ('id', 'title', 'doctype', 'date')} for d in docs], 'entities': [], 'relations': []})
        with tempfile.TemporaryDirectory() as tmp:
            cj = os.path.join(tmp, spec['id'] + '.json'); json.dump(case, open(cj, 'w'))
            build(cj, relate, a.out, os.path.join(HERE, 'data', 'rulebook'))
            relate_q(relate, db, "MATCH (k:Case) SET k.built_from = 'client documents', k.folder = $f, k.template = $t", {'f': os.path.basename(os.path.normpath(a.folder)), 't': bool(a.template)}, read=False)
        if a.template:
            print(f'template {os.path.relpath(db, HERE)}: the client without documents or structure'); return
            plain = [d for d in docs if d['doctype'] != 'structure_chart']
            if plain:
                for d in plain:
                    os.symlink(os.path.abspath(os.path.join(a.folder, 'documents', d['file'])), os.path.join(tmp, d['id'] + os.path.splitext(d['file'])[1]))
                r = subprocess.run([sys.executable, os.path.join(HERE, 'casefold', 'ingest.py'), db] + [os.path.join(tmp, d['id'] + os.path.splitext(d['file'])[1]) for d in plain] + ['--relate', relate],
                                   capture_output=True, text=True)
                print(r.stdout.strip() or r.stderr.strip()[-600:])
        for d in docs:
            if d['doctype'] == 'structure_chart':
                propose(relate, db, os.path.join(a.folder, 'documents', d['file']), d['id'], d['title'], d['date'])
                print('\n  Proposals from the structure chart (the compliance officer confirms them):')
                listing(relate, db)
    if a.confirm:
        confirm(relate, db, a.confirm, 'compliance officer')
    review(relate, db, a.on)
    if relate_q(relate, db, "MATCH (p:Proposal {status:'proposed'}) RETURN count(p) AS n")[0]['n']:
        print(f"\nNext: check the proposals, then  python3 casefold/structure_chart.py {os.path.relpath(db, HERE)} --confirm all   (or per id)  "
              f"and  python3 casefold/new_client.py {a.folder} --review")


if __name__ == '__main__':
    main()
