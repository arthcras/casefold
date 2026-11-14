#!/usr/bin/env python3
"""Add text embeddings to case files, computed by a local model, and stored in the case file itself.

Every Document (title + text), every OCR Chunk (from ingest.py) and every law Article (English + original text) gets an
`embedding` property, and the case file gets vector indexes `doc_vec`, `chunk_vec` and `article_vec`. No text leaves the machine: the model runs locally
(sentence-transformers). After the first download of the model weights you can work offline (HF_HUB_OFFLINE=1).

The default model, intfloat/multilingual-e5-small (384 dimensions), is multilingual, so a question in Dutch finds an
article in English and the other way round.

usage:  pip install sentence-transformers            # once (CPU is enough)
        python3 casefold/embed.py cases/*.rl
        python3 casefold/embed.py cases/*.rl --model BAAI/bge-m3
        python3 casefold/embed.py cases/*.rl --model hash   # tests only: deterministic, NOT semantic, no download
"""
import argparse, hashlib, json, math, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_case import find_relate

DEFAULT_MODEL = 'intfloat/multilingual-e5-small'


class Embedder:
    """Local embedding model. e5 models expect 'query: ' / 'passage: ' prefixes; other models get the plain text."""

    def __init__(self, name):
        self.name = name
        if name == 'hash':
            self.dim, self.model = 64, None
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            sys.exit('sentence-transformers is not installed:  pip install sentence-transformers')
        self.model = SentenceTransformer(name, device='cpu')
        self.dim = self.model.get_sentence_embedding_dimension()
        self.e5 = 'e5' in name.lower()

    def encode(self, texts, kind):
        if self.model is None:  # deterministic test vectors from character trigrams; not semantic
            out = []
            for t in texts:
                v = [0.0] * self.dim
                s = t.lower()
                for i in range(max(1, len(s) - 2)):
                    v[int(hashlib.md5(s[i:i + 3].encode()).hexdigest(), 16) % self.dim] += 1.0
                n = math.sqrt(sum(x * x for x in v)) or 1.0
                out.append([round(x / n, 6) for x in v])
            return out
        pre = ('query: ' if kind == 'query' else 'passage: ') if self.e5 else ''
        vecs = self.model.encode([pre + t for t in texts], normalize_embeddings=True, batch_size=32, show_progress_bar=False)
        return [[round(float(x), 6) for x in v] for v in vecs]


def relate_rows(relate, db, cypher):
    r = subprocess.run([relate, 'query', '--database', db, '--read-only', '--mode', 'json', '--max-rows', '0', '-c', cypher], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr[-800:])
    i = r.stdout.find('{"data"')
    return json.loads(r.stdout[i:])['data'] if i >= 0 else []


def relate_write(relate, db, script, params):
    tmp, args = [], [relate, 'query', '--database', db]
    try:
        for k, v in params.items():
            fd, p = tempfile.mkstemp(suffix='.json'); os.close(fd); tmp.append(p)
            json.dump(v, open(p, 'w'), separators=(',', ':')); args += ['--fetch-params', f'{k}={p}']
        r = subprocess.run(args, input=script, capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stderr[-800:])
    finally:
        for p in tmp:
            os.remove(p)


def embed_case(relate, db, emb):
    docs = relate_rows(relate, db, "MATCH (d:Document) RETURN d.id AS id, coalesce(d.title,'') + '. ' + coalesce(d.text,'') AS text")
    arts = relate_rows(relate, db, "MATCH (a:Article) RETURN a.id AS id, coalesce(a.ref,'') + '. ' + coalesce(a.text_en,'') + ' ' + coalesce(a.text_local,'') AS text")
    chunks = relate_rows(relate, db, "MATCH (d:Document)-[:HAS_CHUNK]->(k:Chunk) RETURN k.id AS id, coalesce(d.title,'') + ': ' + k.text AS text")
    d = [{'id': r['id'], 'v': v} for r, v in zip(docs, emb.encode([r['text'] for r in docs], 'passage'))]
    k = [{'id': r['id'], 'v': v} for r, v in zip(chunks, emb.encode([r['text'] for r in chunks], 'passage'))] if chunks else []
    a = [{'id': r['id'], 'v': v} for r, v in zip(arts, emb.encode([r['text'] for r in arts], 'passage'))]
    relate_write(relate, db, """
UNWIND $d AS x MATCH (n:Document {id:x.id}) SET n.embedding = x.v;
UNWIND $a AS x MATCH (n:Article {id:x.id}) SET n.embedding = x.v;
UNWIND $k AS x MATCH (n:Chunk {id:x.id}) SET n.embedding = x.v;
CREATE VECTOR INDEX chunk_vec IF NOT EXISTS FOR (n:Chunk) ON (n.embedding);
CREATE VECTOR INDEX doc_vec IF NOT EXISTS FOR (n:Document) ON (n.embedding);
CREATE VECTOR INDEX article_vec IF NOT EXISTS FOR (n:Article) ON (n.embedding);
MATCH (k:Case) SET k.embedding_model = $model, k.embedding_dim = $dim
""", {'d': d, 'a': a, 'k': k, 'model': emb.name, 'dim': emb.dim})
    print(f'{db}: {len(d)} documents, {len(k)} OCR chunks, {len(a)} articles embedded with {emb.name} ({emb.dim} dims)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cases', nargs='+'); ap.add_argument('--model', default=DEFAULT_MODEL); ap.add_argument('--relate')
    a = ap.parse_args()
    relate, emb = find_relate(a.relate), Embedder(a.model)
    for db in a.cases:
        embed_case(relate, db, emb)


if __name__ == '__main__':
    main()
