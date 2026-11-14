#!/usr/bin/env python3
"""Read a law into its own Relate file: one file per law, version and language.

    python3 casefold/law_ingest.py laws/sources/wwft-2026-01-01-nl.pdf --law NL:wwft --version 2026-01-01 --lang nl
    python3 casefold/law_ingest.py laws/sources/amlr-nl.pdf --law EU:amlr --version 2027-07-10 --lang nl --ocr
    python3 casefold/law_ingest.py laws/sources/amlr-en.pdf --law EU:amlr --version 2027-07-10 --lang en

Text: pdftotext when the PDF has a text layer; tesseract (nld or eng, 300 dpi) when it has none, or always with --ocr.
The text is split into articles ("Artikel 16" / "Article 69"), paragraphs (leden: "1." / "1") and points
(onderdelen: "a." / "(a)"). The result:

    laws/<law>@<version>-<lang>.rl    (:LawVersion)-[:HAS_ARTICLE]->(:LawArticle)-[:HAS_PARAGRAPH]->(:LawParagraph)-[:HAS_POINT]->(:LawPoint)
    laws/<law>@<version>-<lang>.json  the same, for build_duties.py

Every node keeps the verbatim text as extracted; the version keeps the source file's sha256, the method (pdftotext or
tesseract) and, for OCR, the mean word confidence. Nothing here is client data.
"""
import argparse, hashlib, json, os, re, subprocess, sys, tempfile
from build_case import find_relate, run, HERE

NOISE = [r'^wetten\.nl\s*-', r'^Pagina \d+ van \d+', r'^Geldend van ', r'^\d{2}-\d{2}-\d{4}$', r'^Publicatieblad van de Europese Unie',
         r'^Official Journal of the European Union', r'^NL$', r'^EN$', r'^L \d+/\d+', r'^ELI: ', r'^\d+/\d+$', r'^https?://']
ART = {'nl': re.compile(r'^\s*Artikel\s+(\d+[a-z]{0,3})\s*\.?\s*(.*)$'), 'en': re.compile(r'^\s*Article\s+(\d+[a-z]{0,3})\s*\.?\s*(.*)$')}
PARA = re.compile(r'^\s*(\d{1,2})[.)]?\s+(\S.*)?$')
POINT = re.compile(r'^\s*\(?([a-z]{1,2}|[ivx]{1,4})[.)]\s+(\S.*)$')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def pdf_text(path):
    r = subprocess.run(['pdftotext', '-enc', 'UTF-8', path, '-'], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ''


def ocr(path, lang):
    """tesseract page by page; returns the text and the mean word confidence."""
    tl = {'nl': 'nld', 'en': 'eng'}.get(lang, 'nld+eng')
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(['pdftoppm', '-r', '300', '-png', path, os.path.join(d, 'p')], check=True)
        pages, confs = [], []
        for img in sorted(f for f in os.listdir(d) if f.endswith('.png')):
            r = subprocess.run(['tesseract', os.path.join(d, img), '-', '-l', tl, '--psm', '4', 'tsv'], capture_output=True, text=True, check=True)
            lines, cur = [], {}
            for row in r.stdout.splitlines()[1:]:
                c = row.split('\t')
                if len(c) < 12 or not c[11].strip():
                    continue
                key = (c[2], c[3], c[4])          # block, paragraph, line
                cur.setdefault(key, []).append(c[11])
                if float(c[10]) >= 0:
                    confs.append(float(c[10]))
            pages.append('\n'.join(' '.join(w) for w in cur.values()))
        return '\n'.join(pages), (round(sum(confs) / len(confs), 1) if confs else None)


def clean(text):
    out = []
    for line in text.replace('\f', '\n').splitlines():
        s = line.strip()
        if not s or any(re.search(p, s) for p in NOISE):
            continue
        out.append(s)
    return out


def parse(lines, lang, eu=False):
    """Articles, paragraphs and points from the cleaned lines. A heading on the line after 'Article 69' (EU style) is kept.
    eu: an EU regulation, where an article starts on a line that is exactly 'Artikel N' / 'Article N', numbered 1, 2, 3, ... in order;
    anything else that looks like it is a cross-reference in the running text."""
    arts, cur = [], None
    for s in lines:
        m = ART[lang].match(s)
        if eu and m and (m.group(2) or not m.group(1).isdigit() or int(m.group(1)) != len(arts) + 1):
            m = None
        if m and (not m.group(2) or len(m.group(2)) < 120):
            cur = {'number': m.group(1), 'heading': m.group(2).strip(' .'), 'lines': []}
            arts.append(cur)
            continue
        if cur is not None:
            cur['lines'].append(s)
    seen, out = set(), []
    for a in arts:
        if a['number'] in seen:            # a cross-reference that looked like a heading: keep the first
            continue
        seen.add(a['number'])
        body = a['lines']
        if (lang == 'en' or eu) and not a['heading'] and body and not PARA.match(body[0]) and len(body[0]) < 120:
            a['heading'] = body.pop(0)
        paras, p, pt = [], None, None
        intro = []
        for s in body:
            if re.fullmatch(r'\d{1,2}\.', s):          # EU style: the paragraph number on its own line
                s = s + ' '
            mp, mo = PARA.match(s), POINT.match(s)
            if mp and (p is None and int(mp.group(1)) <= 2 or p is not None and int(p['number']) < int(mp.group(1)) <= int(p['number']) + 3):
                p = {'number': mp.group(1), 'text': mp.group(2) or '', 'points': []}; paras.append(p); pt = None
            elif mo and p is not None:
                pt = {'label': mo.group(1), 'text': mo.group(2)}; p['points'].append(pt)
            elif pt is not None:
                pt['text'] += ' ' + s
            elif p is not None:
                p['text'] = (p['text'] + ' ' + s).strip()
            else:
                intro.append(s)
        text = ' '.join(intro) if not paras else ' '.join(intro + [f"{x['number']}. {x['text']}" + ''.join(f" {y['label']}. {y['text']}" for y in x['points']) for x in paras])
        out.append({'number': a['number'], 'heading': a['heading'], 'text': re.sub(r'\s+', ' ', text).strip(), 'paragraphs': paras})
    return out


def text_of(el):
    """All text of an element, without the meta-data blocks, whitespace normalised."""
    parts = []
    def walk(e):
        if e.tag == 'meta-data':
            return
        if e.text: parts.append(e.text)
        for c in e: 
            walk(c)
            if c.tail: parts.append(c.tail)
    walk(el)
    return re.sub(r'\s+', ' ', ''.join(parts)).strip()


def parse_bwb_xml(path):
    """The official BWB XML of wetten.overheid.nl: <artikel><kop><nr/></kop><lid><lidnr/><al/><lijst><li><li.nr/><al/></li></lijst></lid></artikel>."""
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    meta = {'version': root.get('inwerkingtreding'), 'bwb': root.get('bwb-id'), 'title': text_of(root.find('.//citeertitel')) if root.find('.//citeertitel') is not None else ''}
    out, seen = [], set()
    for a in root.iter('artikel'):
        kop = a.find('kop')
        nr = (kop.findtext('nr') or '').strip() if kop is not None else ''
        if not nr or nr in seen:
            continue
        seen.add(nr)
        heading = text_of(kop.find('titel')) if kop is not None and kop.find('titel') is not None else ''
        def points(el):
            pts = []
            for lijst in el.findall('lijst'):
                for li in lijst.findall('li'):
                    label = (li.findtext('li.nr') or '').strip().rstrip('.')
                    body = ' '.join(text_of(c) for c in li if c.tag not in ('li.nr', 'meta-data'))
                    pts.append({'label': label, 'text': body})
            return pts
        paras = []
        for lid in a.findall('lid'):
            num = (lid.findtext('lidnr') or '').strip().rstrip('.')
            al = ' '.join(text_of(c) for c in lid if c.tag == 'al')
            paras.append({'number': num, 'text': al, 'points': points(lid)})
        if paras:
            text = ' '.join(f"{p['number']}. {p['text']}" + ''.join(f" {q['label']}. {q['text']}" for q in p['points']) for p in paras)
        else:
            intro = ' '.join(text_of(c) for c in a if c.tag == 'al')
            pts = points(a)
            if pts:   # an article without leden: its list becomes one unnumbered paragraph
                paras = [{'number': '', 'text': intro, 'points': pts}]
            text = intro + ''.join(f" {q['label']}. {q['text']}" for q in pts)
        out.append({'number': nr, 'heading': heading, 'text': re.sub(r'\s+', ' ', text).strip(), 'paragraphs': paras})
    return out, meta


SCRIPT = """
CREATE CONSTRAINT law_version_id IF NOT EXISTS FOR (n:LawVersion) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT law_article_id IF NOT EXISTS FOR (n:LawArticle) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT law_paragraph_id IF NOT EXISTS FOR (n:LawParagraph) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT law_point_id IF NOT EXISTS FOR (n:LawPoint) REQUIRE n.id IS UNIQUE;
CREATE FULLTEXT INDEX law_text IF NOT EXISTS FOR (n:LawArticle) ON EACH [n.heading, n.text];
MERGE (v:LawVersion {id:$v.id}) SET v += $v;
UNWIND $arts AS a MATCH (v:LawVersion {id:$v.id}) MERGE (x:LawArticle {id:a.id}) SET x.law=$v.law, x.version=$v.version, x.lang=$v.lang, x.number=a.number, x.seq=a.seq, x.heading=a.heading, x.text=a.text MERGE (v)-[:HAS_ARTICLE]->(x);
UNWIND $paras AS p MATCH (a:LawArticle {id:p.article}) MERGE (x:LawParagraph {id:p.id}) SET x.number=p.number, x.seq=p.seq, x.text=p.text MERGE (a)-[:HAS_PARAGRAPH]->(x);
UNWIND $points AS p MATCH (l:LawParagraph {id:p.paragraph}) MERGE (x:LawPoint {id:p.id}) SET x.label=p.label, x.text=p.text MERGE (l)-[:HAS_POINT]->(x);
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source'); ap.add_argument('--law', required=True); ap.add_argument('--version', required=True, help='date the text is valid from')
    ap.add_argument('--valid-to', default=None); ap.add_argument('--lang', default='nl', choices=['nl', 'en'])
    ap.add_argument('--title', default=''); ap.add_argument('--url', default=''); ap.add_argument('--ocr', action='store_true', help='always use tesseract')
    ap.add_argument('--out', default=os.path.join(HERE, 'laws'))
    a = ap.parse_args()
    src = a.source
    if src.lower().endswith('.pdf'):
        text, method, conf = ('', None, None) if a.ocr else (pdf_text(src), 'pdftotext', None)
        pages = max(1, int(subprocess.run(['pdfinfo', src], capture_output=True, text=True).stdout.split('Pages:')[1].split()[0])) if not a.ocr else 1
        if a.ocr or len(text.strip()) < 200 * pages:
            text, conf = ocr(src, a.lang); method = 'tesseract'
    elif src.lower().endswith('.xml'):
        arts, meta = parse_bwb_xml(src); method, conf = 'bwb-xml', None
        a.title = a.title or meta['title']; a.url = a.url or f"https://wetten.overheid.nl/{meta['bwb']}/{meta['version']}"
    else:
        text, method, conf = open(src, encoding='utf-8').read(), 'text', None
    if not src.lower().endswith('.xml'):
        arts = parse(clean(text), a.lang, eu=a.law.startswith('EU:'))
    if not arts:
        sys.exit(f'{src}: no articles found (method {method}); check the file')
    key = f"{a.law}@{a.version}-{a.lang}"
    vid = key
    v = {'id': vid, 'law': a.law, 'version': a.version, 'valid_from': a.version, 'valid_to': a.valid_to, 'lang': a.lang, 'title': a.title, 'url': a.url,
         'source_file': os.path.basename(src), 'sha256': sha256(src), 'method': method, 'ocr_confidence': conf, 'articles': len(arts)}
    A, P, Q = [], [], []
    for seq, x in enumerate(arts, 1):
        aid = f"{vid}:art{x['number']}"
        A.append({'id': aid, 'number': x['number'], 'seq': seq, 'heading': x['heading'], 'text': x['text']})
        for p in x['paragraphs']:
            pid = f"{aid}:{p['number']}"
            P.append({'id': pid, 'article': aid, 'number': p['number'], 'seq': len(P) + 1, 'text': p['text']})
            Q += [{'id': f"{pid}:{q['label']}", 'paragraph': pid, 'label': q['label'], 'text': q['text']} for q in p['points']]
    os.makedirs(a.out, exist_ok=True)
    safe = key.replace(':', '_').replace('/', '-').replace('@', '_')
    db = os.path.join(a.out, safe + '.rl')
    if os.path.exists(db):
        os.remove(db)
    run(find_relate(None), db, {'v': v, 'arts': A, 'paras': P, 'points': Q}, script=SCRIPT)
    json.dump({**v, 'article_list': arts}, open(os.path.join(a.out, safe + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"{key}: {len(A)} articles, {len(P)} paragraphs, {len(Q)} points ({method}{', OCR confidence ' + str(conf) if conf else ''}) -> {db}")


if __name__ == '__main__':
    main()
