#!/usr/bin/env python3
"""Ask a question in your own words, in any language, against one case file: vector search plus the graph around the hits.

The question is embedded with the same local model that embedded the case (stored on the Case node), then:
  - law:  the closest law articles, the obligations they impose, the document types that prove them,
          and whether this client has already delivered each one;
  - docs: the closest passages in the scanned documents (OCR chunks: page, position, OCR confidence) and the persons or
          companies the document mentions; without OCR chunks, the closest documents and the questions they answer.

usage:  python3 casefold/semantic.py cases/nl-kalmora.rl "Moet ik de herkomst van het vermogen van een PEP vaststellen?"
        python3 casefold/semantic.py cases/nl-kalmora.rl "who holds shares through a nominee?" --scope docs
"""
import argparse, json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_case import find_relate
from embed import Embedder, relate_rows

Q_LAW = """
MATCH (a:Article) SEARCH a IN (VECTOR INDEX article_vec FOR $v LIMIT $k) SCORE AS similarity
OPTIONAL MATCH (a)-[i:IMPOSES]->(o:Obligation)-[:PROVEN_BY]->(t:DocumentType)
OPTIONAL MATCH (c:Client)-[:REQUIRES]->(t)
WITH a, similarity, i, o, t, c, EXISTS { (:Document)-[:OF_TYPE]->(t) } AS received
RETURN a.ref AS article, round(similarity, 3) AS similarity, o.text AS obligation, i.condition AS applies,
       collect(DISTINCT t.name + CASE WHEN c IS NULL THEN '' WHEN received THEN ' [in file]' ELSE ' [MISSING]' END) AS documents,
       left(coalesce(i.quote, a.text_en), 160) AS passage, a.source_url AS source
ORDER BY similarity DESC
"""
Q_CHUNKS = """
MATCH (k:Chunk) SEARCH k IN (VECTOR INDEX chunk_vec FOR $v LIMIT $k) SCORE AS similarity
MATCH (d:Document)-[:HAS_CHUNK]->(k)
OPTIONAL MATCH (d)-[:MENTIONS]->(p:Party)
RETURN d.id AS doc, d.file AS file, k.page AS page, k.bbox AS box, round(similarity, 3) AS similarity, k.confidence AS ocr_conf,
       left(replace(k.text, '\n', ' | '), 120) AS text, collect(DISTINCT p.name) AS mentions
ORDER BY similarity DESC
"""
Q_DOCS = """
MATCH (d:Document) SEARCH d IN (VECTOR INDEX doc_vec FOR $v LIMIT $k) SCORE AS similarity
OPTIONAL MATCH (d)-[w:ANSWERS]->(q:Question)
OPTIONAL MATCH (d)-[:MENTIONS]->(p:Party)
RETURN d.id AS doc, d.title AS title, round(similarity, 3) AS similarity, collect(DISTINCT q.id + ' ' + q.text) AS answers,
       collect(DISTINCT p.name) AS mentions
ORDER BY similarity DESC
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('case'); ap.add_argument('question'); ap.add_argument('--scope', choices=['law', 'docs', 'both'], default='both')
    ap.add_argument('--top', type=int, default=4); ap.add_argument('--relate')
    a = ap.parse_args()
    relate = find_relate(a.relate)
    meta = relate_rows(relate, a.case, "MATCH (k:Case) RETURN k.embedding_model AS model")
    model = meta[0]['model'] if meta and meta[0]['model'] else sys.exit('this case has no embeddings yet: run casefold/embed.py first')
    v = Embedder(model).encode([a.question], 'query')[0]
    fd, p = tempfile.mkstemp(suffix='.json'); os.close(fd); json.dump(v, open(p, 'w'))
    try:
        has_chunks = relate_rows(relate, a.case, "MATCH (k:Chunk) WHERE k.embedding IS NOT NULL RETURN count(k) AS n")[0]['n'] > 0
        for name, q in (('Law articles', Q_LAW), ('Documents in the file' + (' (OCR text, page and position)' if has_chunks else ''), Q_CHUNKS if has_chunks else Q_DOCS)):
            if a.scope != 'both' and not name.lower().startswith(a.scope[:3]):
                continue
            print(f'\n== {name} closest to: "{a.question}"  (model {model})')
            r = subprocess.run([relate, 'query', '--database', a.case, '--read-only', '--mode', 'table', '--max-rows', '0', '--fetch-params', f'v={p}',
                                '--param', f'k={a.top}', '-c', q], capture_output=True, text=True)
            print('\n'.join(l for l in (r.stdout or r.stderr).splitlines() if l.startswith(('|', '+')) or 'error' in l.lower()))
    finally:
        os.remove(p)


if __name__ == '__main__':
    main()
