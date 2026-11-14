#!/usr/bin/env python3
"""Read scanned client documents into the case file: detect, OCR with Tesseract, cut into chunks with page, position and
confidence, and store them as (:Document)-[:HAS_CHUNK]->(:Chunk) in the client's own .rl file.

Pipeline per file (data/documents/<case>/<doc-id>.<pdf|png|jpg|tif|txt>):
  1. detect   - Apache Tika (optional, --tika http://127.0.0.1:9998): content type, language and metadata.
                Without Tika: type from the file, language set from the client's jurisdiction.
  2. text     - PDF with a text layer: pdftotext (no OCR needed, confidence 100).
                Scans and image-only PDFs: pdftoppm (300 dpi) -> Tesseract TSV, which gives every word with its box and confidence.
  3. chunks   - one chunk per Tesseract paragraph: text, page, bounding box, mean confidence, number of low-confidence words.
  4. store    - Chunk nodes with a full-text index; the document gets its OCR confidence and page count, and a SHA-256 of the file.
Then run embed.py: it embeds the chunks too, so questions in your own words land on a page and a place in a scan.

Everything runs locally: Tesseract, poppler and (optionally) a local Tika server. Nothing is uploaded.

usage:  python3 casefold/ingest.py cases/nl-kalmora.rl data/documents/nl-kalmora/*
        python3 casefold/ingest.py cases/nl-kalmora.rl data/documents/nl-kalmora/* --lang nld+eng --tika http://127.0.0.1:9998
"""
import argparse, csv, glob, hashlib, io, json, os, shutil, subprocess, sys, tempfile, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_case import find_relate
from embed import relate_rows, relate_write

LANG_BY_JURISDICTION = {'CW': 'nld+eng', 'NL': 'nld+eng', 'MT': 'eng'}   # Tesseract has no Papiamentu model; Maltese is 'mlt' if installed
LOW_CONF = 60


def need(tool):
    if not shutil.which(tool):
        sys.exit(f'{tool} not found. macOS: brew install tesseract tesseract-lang poppler   Debian/Ubuntu: apt install tesseract-ocr tesseract-ocr-nld poppler-utils')


def tika(url, path):
    """Content type, language and a few metadata fields from a local Tika server (tika-server, port 9998)."""
    data = open(path, 'rb').read()
    def put(ep, accept):
        req = urllib.request.Request(url.rstrip('/') + ep, data=data, method='PUT', headers={'Accept': accept})
        return urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'replace')
    meta = json.loads(put('/meta', 'application/json'))
    lang = put('/language/stream', 'text/plain').strip()
    return {'mime': meta.get('Content-Type', ''), 'tika_language': lang, 'producer': meta.get('pdf:producer') or meta.get('producer') or '',
            'created': meta.get('dcterms:created') or meta.get('Creation-Date') or ''}


def pdf_text_pages(path):
    r = subprocess.run(['pdftotext', '-layout', path, '-'], capture_output=True, text=True)
    pages = r.stdout.split('\f')
    return [p for p in pages if p.strip()] if sum(len(p.strip()) for p in pages) > 40 else []


def ocr_image(img, lang, page_no):
    r = subprocess.run(['tesseract', img, 'stdout', '-l', lang, '--psm', '3', 'tsv'], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr[-600:])
    paras = {}
    for w in csv.DictReader(io.StringIO(r.stdout), delimiter='\t', quoting=csv.QUOTE_NONE):
        if w['level'] != '5' or not (w['text'] or '').strip():
            continue
        key = (w['block_num'], w['par_num'])
        p = paras.setdefault(key, {'words': [], 'conf': [], 'box': [10**9, 10**9, 0, 0], 'line': None, 'text': ''})
        x, y, wd, ht = int(w['left']), int(w['top']), int(w['width']), int(w['height'])
        b = p['box']; b[0], b[1], b[2], b[3] = min(b[0], x), min(b[1], y), max(b[2], x + wd), max(b[3], y + ht)
        p['text'] += ('\n' if p['line'] not in (None, w['line_num']) else (' ' if p['text'] else '')) + w['text']
        p['line'] = w['line_num']; p['conf'].append(float(w['conf']))
    out = []
    for (blk, par), p in sorted(paras.items(), key=lambda kv: (kv[1]['box'][1], kv[1]['box'][0])):
        c = p['conf']
        out.append({'page': page_no, 'text': p['text'], 'bbox': p['box'], 'conf': round(sum(c) / len(c), 1), 'low_conf_words': sum(1 for x in c if x < LOW_CONF)})
    return out


def read_file(path, lang):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.txt':
        return 'text/plain', [{'page': 1, 'text': t, 'bbox': None, 'conf': 100.0, 'low_conf_words': 0} for t in open(path, encoding='utf-8').read().split('\n\n') if t.strip()], False
    if ext == '.pdf':
        pages = pdf_text_pages(path)
        if pages:
            ch = []
            for i, pg in enumerate(pages, 1):
                ch += [{'page': i, 'text': t.strip(), 'bbox': None, 'conf': 100.0, 'low_conf_words': 0} for t in pg.split('\n\n') if t.strip()]
            return 'application/pdf', ch, False
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(['pdftoppm', '-r', '300', '-png', path, os.path.join(td, 'p')], check=True)
            ch = []
            for i, img in enumerate(sorted(glob.glob(os.path.join(td, 'p*.png'))), 1):
                ch += ocr_image(img, lang, i)
            return 'application/pdf', ch, True
    return {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.tif': 'image/tiff', '.tiff': 'image/tiff'}.get(ext, 'application/octet-stream'), ocr_image(path, lang, 1), True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('case'); ap.add_argument('files', nargs='+'); ap.add_argument('--lang'); ap.add_argument('--tika'); ap.add_argument('--relate')
    a = ap.parse_args()
    need('tesseract'); need('pdftoppm'); need('pdftotext')
    relate = find_relate(a.relate)
    jur = (relate_rows(relate, a.case, 'MATCH (j:Jurisdiction) RETURN j.code AS code') or [{'code': ''}])[0]['code']
    lang = a.lang or LANG_BY_JURISDICTION.get(jur, 'eng')
    have = subprocess.run(['tesseract', '--list-langs'], capture_output=True, text=True).stdout.split()
    missing = [l for l in lang.split('+') if l not in have]
    if missing:
        sys.exit(f'Tesseract language data missing: {missing}. Install the language packs (e.g. brew install tesseract-lang).')
    known = {r['id'] for r in relate_rows(relate, a.case, 'MATCH (d:Document) RETURN d.id AS id')}
    docs, chunks = [], []
    for f in a.files:
        did = os.path.splitext(os.path.basename(f))[0]
        if did not in known:
            print(f'skip {f}: no Document {did} in this case'); continue
        info = tika(a.tika, f) if a.tika else {}
        mime, ch, ocr = read_file(f, lang)
        conf = round(sum(c['conf'] for c in ch) / len(ch), 1) if ch else 0
        docs.append({'id': did, 'file': os.path.basename(f), 'sha256': hashlib.sha256(open(f, 'rb').read()).hexdigest(), 'mime': info.get('mime') or mime,
                     'ocr': ocr, 'ocr_lang': lang if ocr else '', 'ocr_confidence': conf, 'pages': max([c['page'] for c in ch] or [0]),
                     'tika_language': info.get('tika_language', ''), 'producer': info.get('producer', ''), 'created': info.get('created', ''),
                     'text': '\n'.join(c['text'] for c in ch)})
        for i, c in enumerate(ch, 1):
            chunks.append({'id': f'{did}-p{c["page"]}-c{i}', 'doc': did, **c, 'bbox': c['bbox'] or [], 'lang': lang})
        print(f'{f}: {mime}{" (OCR " + lang + ")" if ocr else ""}, {len(ch)} chunks, mean confidence {conf}, '
              f'{sum(c["low_conf_words"] for c in ch)} words below {LOW_CONF}')
    relate_write(relate, a.case, """
UNWIND $docs AS d MATCH (x:Document {id:d.id}) OPTIONAL MATCH (x)-[:HAS_CHUNK]->(old:Chunk) DETACH DELETE old;
UNWIND $docs AS d MATCH (x:Document {id:d.id}) SET x.file=d.file, x.sha256=d.sha256, x.mime=d.mime, x.ocr=d.ocr, x.ocr_lang=d.ocr_lang,
  x.ocr_confidence=d.ocr_confidence, x.pages=d.pages, x.tika_language=d.tika_language, x.producer=d.producer, x.created=d.created,
  x.text=coalesce(x.text, d.text);
UNWIND $chunks AS c MATCH (x:Document {id:c.doc}) CREATE (k:Chunk {id:c.id, page:c.page, text:c.text, bbox:c.bbox, confidence:c.conf, low_conf_words:c.low_conf_words, lang:c.lang})
  CREATE (x)-[:HAS_CHUNK]->(k);
CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (n:Chunk) ON EACH [n.text]
""", {'docs': docs, 'chunks': chunks})
    print(f'{a.case}: {len(docs)} documents, {len(chunks)} chunks stored')


if __name__ == '__main__':
    main()
