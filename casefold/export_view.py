#!/usr/bin/env python3
"""Prepare the browser viewer: read each case file back (read-only) and write web/data/<case>.json with a Cypher script
and its parameters. The viewer loads Relate's WebAssembly build, runs that script into an in-memory database in the
browser, and from then on every view and every question is a Cypher query running in the page - no server.

Embeddings (from embed.py) are carried along, so the viewer can show "similar passages" with a vector index in the browser.
Also writes web/data/queries.json (the questions from queries/) and web/data/index.json.

usage:  python3 casefold/export_view.py cases/*.rl offices/*.rl
"""
import glob, json, os, re, subprocess, sys
from apply_schema import statements as schema_statements
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_case import find_relate, HERE

Q_NODES = "MATCH (n) RETURN labels(n) AS labels, properties(n) AS p, coalesce(n.id, n.key, n.code) AS key"
Q_RELS = ("MATCH (a)-[r]->(b) RETURN labels(a)[0] + ':' + coalesce(a.id, a.key, a.code) AS s, type(r) AS y, properties(r) AS p, "
          "labels(b)[0] + ':' + coalesce(b.id, b.key, b.code) AS t")
INDEXES = ["CREATE FULLTEXT INDEX doc_text IF NOT EXISTS FOR (n:Document) ON EACH [n.title, n.text]",
           "CREATE FULLTEXT INDEX article_text IF NOT EXISTS FOR (n:Article) ON EACH [n.text_en, n.text_local]",
           "CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (n:Chunk) ON EACH [n.text]"]
VECTORS = {'Document': 'doc_vec', 'Article': 'article_vec', 'Chunk': 'chunk_vec'}
NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


try:
    EXPECTED = json.load(open(os.path.join(HERE, 'tests', 'expected.json'), encoding='utf-8'))
except OSError:
    EXPECTED = {}


CAT_ORDER = {c['id']: i for i, c in enumerate(json.load(open(os.path.join(HERE, 'data', 'sector_taxonomy.json'), encoding='utf-8'))['categories'])}


def q(relate, db, cypher):
    r = subprocess.run([relate, 'query', '--database', db, '--read-only', '--mode', 'json', '--max-rows', '0', '-c', cypher], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr[-800:])
    i = r.stdout.find('{"data"')
    return json.loads(r.stdout[i:])['data'] if i >= 0 else []


def export(relate, db, out):
    cid = os.path.basename(db)[:-3]
    nodes, rels = q(relate, db, Q_NODES), q(relate, db, Q_RELS)
    groups, params, stmts, has_vec = {}, {}, [], set()
    for n in nodes:
        labs = [l for l in n['labels'] if NAME.match(l)]
        p = dict(n['p']); p['_vid'] = f"{n['labels'][0]}:{n['key']}"
        if 'embedding' in p and n['labels'][0] in VECTORS:
            has_vec.add(n['labels'][0])
        groups.setdefault(tuple(labs), []).append(p)
    for i, (labs, ps) in enumerate(sorted(groups.items())):
        params[f'n{i}'] = ps
        stmts.append(f"UNWIND $n{i} AS p CREATE (x:{':'.join(labs)}) SET x = p")
    by_type = {}
    for r in rels:
        by_type.setdefault(r['y'], []).append({'s': r['s'], 't': r['t'], 'p': r['p'] or {}})
    for i, (t, rs) in enumerate(sorted(by_type.items())):
        if not NAME.match(t):
            continue
        params[f'r{i}'] = rs
        stmts.append(f"UNWIND $r{i} AS r MATCH (a) WHERE a._vid = r.s MATCH (b) WHERE b._vid = r.t CREATE (a)-[x:{t}]->(b) SET x = r.p")
    stmts += INDEXES + [f"CREATE VECTOR INDEX {VECTORS[l]} IF NOT EXISTS FOR (n:{l}) ON (n.embedding)" for l in sorted(has_vec)]
    register = any('OfficeFile' in n['labels'] for n in nodes)
    office = None if register or any('Client' in n['labels'] for n in nodes) else next((n['p'].get('name') for n in nodes if 'Institution' in n['labels']), None)
    client = 'Sector register: classification, supervisors and duties' if register else office + ' (office file)' if office else next((n['p'].get('name') for n in nodes if 'Client' in n['labels']), cid)
    template = any('Case' in n['labels'] and n['p'].get('template') for n in nodes)
    if template:
        client += ' · new, from uploaded documents'
    elif any('Case' in n['labels'] and n['p'].get('built_from') for n in nodes):
        client += ' · built from its own documents'
    kind = 'register' if register else 'office' if office else 'case'
    lawv = next((n['p'] for n in nodes if 'LawVersion' in n['labels']), None)
    if lawv:      # a law read in by law_ingest.py: one law, one version, one language
        kind, client = 'law', f"{lawv.get('title') or lawv.get('law')} ({lawv.get('lang')}, valid from {lawv.get('valid_from')}; {lawv.get('method')})"
    stmts += [x for x in schema_statements(kind) if not any(x.split(' IF NOT')[0].endswith(' ' + i.split(' ')[3]) for i in INDEXES)]   # the same keys, constraints and indexes as the file
    rel_file = os.path.relpath(os.path.abspath(db), HERE)
    model = next((n['p'].get('embedding_model') for n in nodes if 'Case' in n['labels']), None)
    json.dump({'case': cid, 'kind': kind, 'client': client, 'file': rel_file, 'embedding_model': model, 'vectors': sorted(has_vec),
               'script': ';\n'.join(stmts), 'params': params}, open(os.path.join(out, cid + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'{cid}: {len(nodes)} nodes, {len(rels)} relationships, vectors: {", ".join(sorted(has_vec)) or "none"}')
    first = lambda lab, key: next((n['p'].get(key) for n in nodes if lab in n['labels']), None)
    exp = EXPECTED.get(cid, {})
    cat = next((n['p'] for n in nodes if 'SectorCategory' in n['labels']), {}) if kind != 'register' else {}
    sec = next((n['p'] for n in nodes if 'Sector' in n['labels']), {}) if kind != 'register' else {}
    regs = {f"Regulator:{n['key']}": n['p'] for n in nodes if 'Regulator' in n['labels']}
    sups = [{'short': regs[r['s']].get('short'), 'name': regs[r['s']].get('name'), 'role': (r['p'] or {}).get('role'), 'aml': bool((r['p'] or {}).get('aml'))}
            for r in rels if r['y'] == 'SUPERVISES' and r['s'] in regs] if kind != 'register' else []
    sups = sorted({x['short']: x for x in sups}.values(), key=lambda x: not x['aml'])
    lic = next((n for n in nodes if 'Licence' in n['labels']), None) if kind != 'register' else None
    granted = next((regs.get(r['t'], {}).get('short') for r in rels if r['y'] == 'GRANTED_BY'), None) if lic else None
    lic = {'kind': lic['p'].get('kind'), 'name': lic['p'].get('name'), 'basis': lic['p'].get('basis'), 'granted_by': granted} if lic else None
    return {'case': cid, 'kind': kind, 'client': client, 'template': template, 'office': first('Institution', 'name'), 'category': cat.get('name_nl'), 'category_order': CAT_ORDER.get(cat.get('id'), 99),
            'jurisdiction': 'NL', 'sector_id': sec.get('id'), 'sector_local': sec.get('local'), 'supervisors': sups, 'expected': sec.get('expected_supervisor'), 'licence': lic, 'supervisor': first('Regulator', 'short') or first('Regulator', 'name'),
            'sector': first('Sector', 'name'), 'obliged_from': first('Sector', 'obliged_from'), 'scenario': exp.get('scenario'), 'test': cid in EXPECTED}


def main():
    relate = find_relate(os.environ.get('RELATE_BIN'))
    out = os.path.join(HERE, 'web', 'data'); os.makedirs(out, exist_ok=True)
    index = [export(relate, db, out) for db in sys.argv[1:]]
    json.dump(index, open(os.path.join(out, 'index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    import shutil   # the sources the viewer reads into the graph when it opens: the example company, its procedure, enforcement cases
    if os.path.isdir(os.path.join(HERE, 'data', 'sources')):
        shutil.rmtree(os.path.join(out, 'sources'), ignore_errors=True); shutil.copytree(os.path.join(HERE, 'data', 'sources'), os.path.join(out, 'sources'))
    qs = []
    for f in sorted(glob.glob(os.path.join(HERE, 'queries', '*.cypher'))) + sorted(glob.glob(os.path.join(HERE, 'queries', 'office', '*.cypher'))) + sorted(glob.glob(os.path.join(HERE, 'queries', 'register', '*.cypher'))) + sorted(glob.glob(os.path.join(HERE, 'queries', 'explore', '*.cypher'))) + sorted(glob.glob(os.path.join(HERE, 'queries', 'law', '*.cypher'))):
        text = open(f, encoding='utf-8').read()
        desc = text.splitlines()[0].lstrip('/ ').strip()
        scope = {'office': 'office', 'register': 'register', 'explore': 'explore', 'law': 'law'}.get(os.path.basename(os.path.dirname(f)), 'case')
        qs.append({'id': {'office': 'o', 'register': 'r', 'explore': 'x', 'law': 'l'}.get(scope, '') + os.path.basename(f)[:2], 'scope': scope, 'title': desc, 'params': sorted(set(re.findall(r'\$([a-z_]+)', text))), 'cypher': text,
                   **({'from': m.group(1).strip(), 'yields': m.group(2).strip()} if (m := re.search(r'^// from: (.*?) \| yields: (.*)$', text, re.M)) else {})})
    json.dump(qs, open(os.path.join(out, 'queries.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
