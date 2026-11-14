#!/usr/bin/env python3
"""Read a client's structure chart into the client's own graph file, as proposals that the compliance officer confirms.

A structure chart is the drawing a client delivers: a box per party, a line per ownership or control relation, a label on
the line (60%, "veto", "board, exercises 100% of votes") and an arrow pointing to what is owned or controlled. This script
reads a chart that is a vector PDF (drawn in PowerPoint, Visio, Word, Lucidchart and saved as PDF). It runs locally and uses
no AI and no web service: boxes are the PDF's rectangles, relations are its line paths, the arrow decides the direction and
the nearest text decides the label.

  1. propose   every box and every line becomes a Chunk of the chart document (page, position, the text as drawn), and a
               Proposal that is STATED_IN that chunk:  a party (name, person/company/foundation, country) or a relation
               (OWNS {pct, votes}, CONTROLS {basis}, BOARD_OF {votes}). Nothing in the client's structure changes yet.
  2. confirm   the compliance officer confirms all proposals or some of them. Only then are the Party nodes and the OWNS,
               CONTROLS and BOARD_OF relationships written, each with the chart as its source and the chunk as its evidence.

usage:  python3 casefold/structure_chart.py cases/<client>.rl chart.pdf                 # propose (prints the proposals)
        python3 casefold/structure_chart.py cases/<client>.rl --list                    # the proposals and their status
        python3 casefold/structure_chart.py cases/<client>.rl --confirm all             # or --confirm SC-3 SC-7 ...
        python3 casefold/structure_chart.py cases/<client>.rl --reject SC-12

Needs pdfplumber (pip install pdfplumber). A scanned chart (an image without vector lines) cannot be read this way: let the
agent propose the facts with the review prompt, or enter them by hand; they go through the same confirmation.
"""
import argparse, hashlib, json, math, os, re, subprocess, sys, tempfile
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_case import find_relate

COUNTRIES = {'netherlands': 'NL', 'the netherlands': 'NL', 'nederland': 'NL', 'curaçao': 'CW', 'curacao': 'CW', 'cyprus': 'CY',
             'panama': 'PA', 'british virgin islands': 'VG', 'bvi': 'VG', 'malta': 'MT', 'luxembourg': 'LU', 'belgium': 'BE',
             'germany': 'DE', 'united kingdom': 'GB', 'jersey': 'JE', 'guernsey': 'GG', 'cayman islands': 'KY', 'switzerland': 'CH',
             'ireland': 'IE', 'united states': 'US', 'aruba': 'AW', 'sint maarten': 'SX'}
KINDS = {'person': 'Person', 'natural person': 'Person', 'company': 'Company', 'foundation': 'Foundation', 'stichting': 'Foundation',
         'trust': 'Group', 'partnership': 'Group', 'association': 'Group'}
COMPANY_SUFFIX = re.compile(r'\b(B\.?V\.?|N\.?V\.?|Ltd\.?|Limited|S\.?A\.?|GmbH|LLC|Inc\.?|Corp\.?|plc|Holding[s]?)\b', re.I)


def relate_q(relate, db, cypher, params=None, read=True):
    args, tmp = [relate, 'query', '--database', db, '--mode', 'json', '--max-rows', '0'] + (['--read-only'] if read else []), []
    try:
        for k, v in (params or {}).items():
            fd, p = tempfile.mkstemp(suffix='.json'); os.close(fd); tmp.append(p)
            json.dump(v, open(p, 'w'), separators=(',', ':')); args += ['--fetch-params', f'{k}={p}']
        r = subprocess.run(args, input=cypher, capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stderr[-800:])
        if not read:
            return []
        i = r.stdout.find('{"data"')
        return json.JSONDecoder().raw_decode(r.stdout[i:])[0]['data'] if i >= 0 else []
    finally:
        for p in tmp:
            os.remove(p)


# ---------------------------------------------------------------- reading the drawing
def near(p, q, tol=1.5):
    return abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol


def seg_dist(p, a, b):
    ax, ay, bx, by, px, py = *a, *b, *p
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def text_lines(words):
    """Group words into lines (same baseline, small gaps)."""
    out = []
    for w in sorted(words, key=lambda w: (round(w['top']), w['x0'])):
        for l in out:
            if abs(l['top'] - w['top']) < 2 and 0 <= w['x0'] - l['x1'] < 9:
                l['words'].append(w); l['x1'] = w['x1']; l['bottom'] = max(l['bottom'], w['bottom']); break
        else:
            out.append({'words': [w], 'x0': w['x0'], 'x1': w['x1'], 'top': w['top'], 'bottom': w['bottom']})
    for l in out:
        l['text'] = ' '.join(w['text'] for w in l['words'])
        l['bold'] = all('Bold' in w.get('fontname', '') for w in l['words'])
    return out


def read_chart(path):
    try:
        import pdfplumber
    except ImportError:
        sys.exit('pdfplumber is needed to read a structure chart: pip install pdfplumber')
    boxes, rels, pages = [], [], 0
    with pdfplumber.open(path) as pdf:
        for pno, pg in enumerate(pdf.pages, 1):
            pages += 1
            words = pg.extract_words(extra_attrs=['fontname', 'size'])
            rects = [r for r in pg.rects if r['width'] > 40 and r['height'] > 15]
            inside = lambda w, r: w['x0'] >= r['x0'] - 1 and w['x1'] <= r['x1'] + 1 and w['top'] >= r['top'] - 1 and w['bottom'] <= r['bottom'] + 1
            pb = []
            for r in rects:
                ls = text_lines([w for w in words if inside(w, r)])
                if not ls:
                    continue
                name_lines = [l for l in ls if l['bold']] or ls[:1]
                rest = [l for l in ls if l not in name_lines]
                pb.append({'page': pno, 'bbox': [round(r['x0'], 1), round(r['top'], 1), round(r['x1'], 1), round(r['bottom'], 1)],
                           'name': ' '.join(l['text'] for l in name_lines), 'detail': ' · '.join(l['text'] for l in rest),
                           'text': ' / '.join(l['text'] for l in ls)})
            # line paths: join segments that meet at a bend in open space (not at a box, where several arrows may end at one point)
            box_at = lambda p: next((b for b in pb if b['bbox'][0] - 4 <= p[0] <= b['bbox'][2] + 4 and b['bbox'][1] - 4 <= p[1] <= b['bbox'][3] + 4), None)
            segs = [((l['pts'][0][0], l['pts'][0][1]), (l['pts'][-1][0], l['pts'][-1][1]), bool(l.get('dash') and l['dash'][0])) for l in pg.lines]
            parent = list(range(len(segs)))
            def root(i):
                while parent[i] != i:
                    parent[i] = parent[parent[i]]; i = parent[i]
                return i
            ends = [(i, e) for i, s_ in enumerate(segs) for e in s_[:2]]
            for i, e in ends:
                if box_at(e):
                    continue
                meet = [j for j, f in ends if near(e, f) and j != i]
                if len(meet) == 1:
                    parent[root(i)] = root(meet[0])
            groups = {}
            for i in range(len(segs)):
                groups.setdefault(root(i), []).append(i)
            chains = []
            for idx in groups.values():
                ss = [segs[i] for i in idx]
                pts = [p for s_ in ss for p in s_[:2]]
                free = [p for p in pts if sum(near(p, q) for q in pts) == 1]   # the two ends of the path
                if len(free) != 2:
                    continue
                chains.append({'pts': free, 'segs': [(s_[0], s_[1]) for s_ in ss], 'dashed': any(s_[2] for s_ in ss)})
            heads = [c for c in pg.curves if c.get('fill') and (c['x1'] - c['x0']) < 16 and (c['bottom'] - c['top']) < 16]
            free = [l for l in text_lines([w for w in words if not any(inside(w, r) for r in rects)])]
            for c in chains:
                ends = [c['pts'][0], c['pts'][-1]]
                arrow = [any(any(near(e, v, 2.5) for v in h['pts']) for h in heads) for e in ends]
                b0, b1 = box_at(ends[0]), box_at(ends[1])
                if not b0 or not b1 or b0 is b1:
                    continue
                if arrow[0] and not arrow[1]: src, dst, how = b1, b0, 'arrow'
                elif arrow[1] and not arrow[0]: src, dst, how = b0, b1, 'arrow'
                else:
                    (src, dst), how = ((b0, b1) if b0['bbox'][1] < b1['bbox'][1] else (b1, b0)), 'position (no arrow: the upper box owns the lower)'
                rels.append({'page': pno, 'src': src, 'dst': dst, 'how': how, 'dashed': c['dashed'], 'segs': c['segs'], 'labels': []})
            for l in free:     # a label belongs to the nearest line path within 32 points
                anchors = [(l['x0'], (l['top'] + l['bottom']) / 2), (l['x1'], (l['top'] + l['bottom']) / 2)]
                best = min(((min(seg_dist(p, a, b) for p in anchors for a, b in r['segs']), r) for r in rels if r['page'] == pno), default=(99, None), key=lambda x: x[0])
                if best[1] is not None and best[0] < 32:
                    best[1]['labels'].append(l)
            boxes += pb
    for r in rels:
        r['label'] = ' '.join(l['text'] for l in sorted(r['labels'], key=lambda l: l['top']))
        xs = [p for s in r['segs'] for p in s] + [(l['x0'], l['top']) for l in r['labels']] + [(l['x1'], l['bottom']) for l in r['labels']]
        r['bbox'] = [round(min(p[0] for p in xs), 1), round(min(p[1] for p in xs), 1), round(max(p[0] for p in xs), 1), round(max(p[1] for p in xs), 1)]
    return boxes, rels, pages


# ---------------------------------------------------------------- what the drawing says
def party_of(box, client_name):
    d = box['detail'].lower()
    kind = next((v for k, v in KINDS.items() if re.search(r'\b' + k + r'\b', d)), None)
    if not kind:
        kind = 'Company' if COMPANY_SUFFIX.search(box['name']) else 'Foundation' if box['name'].lower().startswith('stichting') else 'Person'
    country = next((v for k, v in sorted(COUNTRIES.items(), key=lambda x: -len(x[0])) if k in d), None)
    is_client = 'client' in d.split(' · ') or norm(box['name']) == norm(client_name)
    return {'name': box['name'], 'kind': kind, 'country': country, 'client': is_client}


def relation_of(label, dashed):
    t = label.lower()
    pct = re.search(r'(\d+(?:[.,]\d+)?)\s*%', t)
    pct = float(pct.group(1).replace(',', '.')) if pct else None
    pct = int(pct) if pct is not None and pct.is_integer() else pct
    if re.search(r'\bveto\b|\bcontrol|\bzeggenschap|\bdecision right', t):
        return {'type': 'CONTROLS', 'basis': label, 'means': 'as drawn in the structure chart'}
    if re.search(r'\bboard\b|\bbestuur', t):
        v = re.search(r'(\d+)\s*%\s*of\s*(?:the\s*)?votes', t)
        return {'type': 'BOARD_OF', 'votes': int(v.group(1)) if v else pct}
    if re.search(r'depositary receipt|certificat', t):
        return {'type': 'OWNS', 'pct': pct, 'votes': 0 if re.search(r'no votes|without vot|zonder stem', t) else pct, 'kind': 'economic'}
    if pct is None:
        return {'type': 'OWNS', 'pct': None, 'votes': None, 'kind': 'legal', 'unclear': True}
    return {'type': 'OWNS', 'pct': pct, 'votes': pct, 'kind': 'legal'}


def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def slug(name):
    return 'P_' + re.sub(r'[^A-Z0-9]+', '_', name.upper()).strip('_')[:40]


# ---------------------------------------------------------------- writing to the graph
PROPOSE = """
MATCH (c:Client) MERGE (d:Document {id:$doc.id}) ON CREATE SET d.title=$doc.title, d.date=$doc.date
SET d.file=$doc.file, d.sha256=$doc.sha256, d.pages=$doc.pages, d.mime='application/pdf', d.ocr=false, d.text=$doc.text, d.read_by='structure_chart.py (vector PDF)'
MERGE (c)-[:HAS_DOCUMENT]->(d)
WITH d MATCH (t:DocumentType {key:'structure_chart'}) MERGE (d)-[:OF_TYPE]->(t);
MATCH (d:Document {id:$doc.id}) OPTIONAL MATCH (d)-[:HAS_CHUNK]->(old:Chunk) OPTIONAL MATCH (p:Proposal)-[:STATED_IN]->(old) WHERE p.status = 'proposed' DETACH DELETE p, old;
UNWIND $chunks AS k MATCH (d:Document {id:$doc.id}) MERGE (x:Chunk {id:k.id}) SET x.page=k.page, x.text=k.text, x.bbox=k.bbox, x.kind=k.kind, x.confidence=100, x.low_conf_words=0, x.lang='und'
  MERGE (d)-[:HAS_CHUNK]->(x);
UNWIND $props AS p MATCH (k:Chunk {id:p.chunk}) MERGE (x:Proposal {id:p.id}) ON CREATE SET x.status='proposed'
  SET x.kind=p.kind, x.from_name=p.from_name, x.to_name=p.to_name, x.party_kind=p.party_kind, x.country=p.country, x.is_client=p.is_client,
      x.pct=p.pct, x.votes=p.votes, x.own_kind=p.own_kind, x.basis=p.basis, x.direction=p.direction, x.unclear=p.unclear, x.text=p.text,
      x.method='structure chart, vector PDF', x.made=$now
  MERGE (x)-[:STATED_IN]->(k);
CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (n:Chunk) ON EACH [n.text]
"""

CONFIRM = """
UNWIND [p IN $parties WHERE NOT p.is_client] AS p MERGE (x:Party {id:p.pid}) ON CREATE SET x.name=p.name, x.kind=p.kind, x.country=p.country, x.pep=false, x.listed=false;
MATCH (x:Party {kind:'Person'}) SET x:Person;
MATCH (x:Party {kind:'Company'}) SET x:Company;
MATCH (x:Party {kind:'Foundation'}) SET x:Foundation;
MATCH (x:Party {kind:'Group'}) SET x:Group;
UNWIND $rels AS r MATCH (a:Party {id:r.from}) MATCH (b) WHERE (b:Party AND b.id = r.to) OR (b:Client AND r.to = 'client')
  FOREACH (_ IN CASE WHEN r.type = 'OWNS' THEN [1] ELSE [] END | MERGE (a)-[x:OWNS]->(b) SET x.pct=r.pct, x.votes=r.votes, x.kind=r.own_kind, x.lender=false, x.source=$doc, x.where=r.where, x.evidence=r.chunk)
  FOREACH (_ IN CASE WHEN r.type = 'CONTROLS' THEN [1] ELSE [] END | MERGE (a)-[x:CONTROLS]->(b) SET x.basis=r.basis, x.means=r.means, x.source=$doc, x.where=r.where, x.evidence=r.chunk)
  FOREACH (_ IN CASE WHEN r.type = 'BOARD_OF' THEN [1] ELSE [] END | MERGE (a)-[x:BOARD_OF]->(b) SET x.votes=r.votes, x.source=$doc, x.where=r.where, x.evidence=r.chunk);
UNWIND $rels AS r MATCH (d:Document {id:$doc}), (a:Party {id:r.from}) MERGE (d)-[:MENTIONS]->(a);
UNWIND $ids AS i MATCH (p:Proposal {id:i}) SET p.status='confirmed', p.confirmed_by=$by, p.confirmed_at=$now;
UNWIND $parties AS p MATCH (x:Proposal {id:p.prop}) MATCH (n) WHERE (n:Party AND n.id = p.pid) OR (n:Client AND p.is_client) MERGE (x)-[:CREATED]->(n)
"""


def propose(relate, db, chart, doc_id, title, date):
    boxes, rels, pages = read_chart(chart)
    client = relate_q(relate, db, 'MATCH (c:Client) RETURN c.name AS name')[0]['name']
    if not doc_id:
        have = relate_q(relate, db, "MATCH (d:Document)-[:OF_TYPE]->(:DocumentType {key:'structure_chart'}) RETURN d.id AS id")
        ids = [r['id'] for r in relate_q(relate, db, 'MATCH (d:Document) RETURN d.id AS id')]
        doc_id = have[0]['id'] if have else 'D' + str(1 + max([int(i[1:]) for i in ids if re.fullmatch(r'D\d+', i)] or [0]))
    chunks, props, n = [], [], 0
    for i, b in enumerate(boxes, 1):
        p = party_of(b, client)
        cid = f'{doc_id}-p{b["page"]}-box{i}'
        b['cid'], b['party'] = cid, p
        chunks.append({'id': cid, 'page': b['page'], 'text': b['text'], 'bbox': b['bbox'], 'kind': 'chart_box'})
        n += 1
        props.append({'id': f'SC-{n}', 'chunk': cid, 'kind': 'party', 'from_name': p['name'], 'to_name': None, 'party_kind': p['kind'],
                      'country': p['country'], 'is_client': p['client'], 'text': b['text']})
    for i, r in enumerate(rels, 1):
        rel = relation_of(r['label'], r['dashed'])
        cid = f'{doc_id}-p{r["page"]}-line{i}'
        text = f'{r["src"]["name"]} → {r["dst"]["name"]}: {r["label"] or "(no label)"}'
        chunks.append({'id': cid, 'page': r['page'], 'text': text, 'bbox': r['bbox'], 'kind': 'chart_line'})
        n += 1
        props.append({'id': f'SC-{n}', 'chunk': cid, 'kind': rel['type'], 'from_name': r['src']['name'], 'to_name': r['dst']['name'],
                      'pct': rel.get('pct'), 'votes': rel.get('votes'), 'own_kind': rel.get('kind'), 'basis': rel.get('basis'),
                      'direction': r['how'], 'unclear': rel.get('unclear', False), 'text': text})
    doc = {'id': doc_id, 'title': title or 'Structure chart', 'date': date, 'file': os.path.basename(chart),
           'sha256': hashlib.sha256(open(chart, 'rb').read()).hexdigest(), 'pages': pages, 'text': '\n'.join(c['text'] for c in chunks)}
    relate_q(relate, db, PROPOSE, {'doc': doc, 'chunks': chunks, 'props': props, 'now': now()}, read=False)
    print(f'{os.path.basename(chart)} -> Document {doc_id}: {len(boxes)} boxes, {len(rels)} lines, {len(props)} proposals (nothing confirmed yet)')
    return doc_id


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def listing(relate, db):
    rows = relate_q(relate, db, """MATCH (p:Proposal)-[:STATED_IN]->(k:Chunk)<-[:HAS_CHUNK]-(d:Document)
RETURN p.id AS id, p.status AS status, p.kind AS kind, p.from_name AS frm, p.to_name AS to, p.party_kind AS pk, p.country AS country, p.is_client AS client,
       p.pct AS pct, p.votes AS votes, p.basis AS basis, p.unclear AS unclear, d.id AS doc, k.page AS page, k.bbox AS bbox""")
    rows.sort(key=lambda r: int(r['id'].split('-')[1]))
    for r in rows:
        where = f"{r['doc']} p.{r['page']} at ({r['bbox'][0]:.0f},{r['bbox'][1]:.0f})"
        if r['kind'] == 'party':
            what = f"party   {r['frm']} ({r['pk']}{', ' + r['country'] if r['country'] else ''}{', the client' if r['client'] else ''})"
        elif r['kind'] == 'OWNS':
            what = f"OWNS    {r['frm']} -> {r['to']}: {r['pct'] if r['pct'] is not None else '?'}% of the shares, {r['votes'] if r['votes'] is not None else '?'}% of the votes" + (' (label unclear: check)' if r['unclear'] else '')
        elif r['kind'] == 'CONTROLS':
            what = f"CONTROLS {r['frm']} -> {r['to']}: {r['basis']}"
        else:
            what = f"BOARD_OF {r['frm']} -> {r['to']}: exercises {r['votes']}% of the votes"
        print(f"  {r['id']:<6} {r['status']:<10} {what}   [{where}]")
    return rows


def confirm(relate, db, which, by):
    rows = relate_q(relate, db, """MATCH (p:Proposal)-[:STATED_IN]->(k:Chunk)<-[:HAS_CHUNK]-(d:Document)
RETURN p.id AS id, p.status AS status, p.kind AS kind, p.from_name AS frm, p.to_name AS to, p.party_kind AS pk, p.country AS country, p.is_client AS client,
       p.pct AS pct, p.votes AS votes, p.own_kind AS own_kind, p.basis AS basis, d.id AS doc, k.id AS chunk, k.page AS page, k.bbox AS bbox""")
    chosen = [r for r in rows if r['status'] == 'proposed' and (which == ['all'] or r['id'] in which)]
    existing = {norm(r['name']): r['id'] for r in relate_q(relate, db, 'MATCH (p:Party) RETURN p.id AS id, p.name AS name')}
    client = norm(relate_q(relate, db, 'MATCH (c:Client) RETURN c.name AS name')[0]['name'])
    party_rows = {norm(r['frm']): r for r in rows if r['kind'] == 'party'}
    def pid(name):
        return 'client' if norm(name) == client else existing.get(norm(name)) or slug(name)
    parties, rels = [], []
    for r in chosen:
        if r['kind'] == 'party':
            parties.append({'prop': r['id'], 'pid': pid(r['frm']), 'name': r['frm'], 'kind': r['pk'], 'country': r['country'], 'is_client': bool(r['client']) or pid(r['frm']) == 'client'})
    for r in chosen:
        if r['kind'] != 'party':
            for end in (r['frm'], r['to']):     # a relation needs both parties: confirming it confirms its boxes too
                pr = party_rows.get(norm(end))
                if pr and pr['status'] == 'proposed' and pr['id'] not in {p['prop'] for p in parties}:
                    parties.append({'prop': pr['id'], 'pid': pid(end), 'name': pr['frm'], 'kind': pr['pk'], 'country': pr['country'], 'is_client': bool(pr['client']) or pid(end) == 'client'})
            rels.append({'type': r['kind'], 'from': pid(r['frm']), 'to': pid(r['to']), 'pct': r['pct'], 'votes': r['votes'], 'own_kind': r['own_kind'] or 'legal',
                         'basis': r['basis'], 'means': 'as drawn in the structure chart', 'chunk': r['chunk'],
                         'where': f"structure chart p.{r['page']}, line at ({r['bbox'][0]:.0f},{r['bbox'][1]:.0f})", 'doc': r['doc']})
    if not chosen:
        print('nothing to confirm'); return
    doc = chosen[0]['doc']
    ids = sorted({r['id'] for r in chosen} | {p['prop'] for p in parties})
    relate_q(relate, db, CONFIRM, {'parties': parties, 'rels': rels, 'ids': ids, 'doc': doc, 'by': by, 'now': now()}, read=False)
    print(f'confirmed {len(ids)} proposals by {by}: {len([p for p in parties if not p["is_client"]])} parties and {len(rels)} relations written to the graph, each with the chart as source')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('case'); ap.add_argument('chart', nargs='?')
    ap.add_argument('--doc', help='Document id for the chart (default: the structure chart already in the file, or the next free D-number)')
    ap.add_argument('--title', default='Structure chart (delivered by the client)'); ap.add_argument('--date')
    ap.add_argument('--list', action='store_true'); ap.add_argument('--confirm', nargs='+', metavar='ID')
    ap.add_argument('--reject', nargs='+', metavar='ID'); ap.add_argument('--by', default='compliance officer')
    ap.add_argument('--relate')
    a = ap.parse_args()
    relate = find_relate(a.relate)
    if a.chart:
        propose(relate, a.case, a.chart, a.doc, a.title, a.date)
    if a.reject:
        relate_q(relate, a.case, "UNWIND $ids AS i MATCH (p:Proposal {id:i}) WHERE p.status = 'proposed' SET p.status='rejected', p.rejected_by=$by, p.rejected_at=$now",
                 {'ids': a.reject, 'by': a.by, 'now': now()}, read=False)
    if a.confirm:
        confirm(relate, a.case, a.confirm, a.by)
    if a.chart or a.list or a.reject or a.confirm:
        listing(relate, a.case)
    else:
        ap.print_help()


if __name__ == '__main__':
    main()
