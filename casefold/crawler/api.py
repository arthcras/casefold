"""Crawler API: trace a wallet on demand.

  POST /trace        {"chain": "tron", "address": "T...", "hops": 3, "top": 5, "direction": "out"}  -> {"id": ...}
  GET  /trace/{id}   status (queued | running | done | failed) and, when done, the trace
  GET  /health       store size and which chains are configured

Runs next to Neo4j on the Casefold server. Settings from the environment (server secrets, never in git):
  CRAWLER_TOKEN      bearer token the app sends (required)
  CRAWLER_DB         SQLite file of the store (default crawler.sqlite)
  CRAWLER_ORIGIN     the app's origin for CORS (e.g. https://casefold.example)
  CRAWLER_OUT        optional folder: each trace is also written as a data/crypto/chain file for the static build
  NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD   optional: write each trace into Neo4j
  TRONGRID_API_KEY   optional: higher Tron limits
Start: uvicorn --factory casefold.crawler.api:make_app --host 127.0.0.1 --port 8090   (behind the server's reverse proxy, HTTPS)
"""
import json, os, re, secrets, threading, uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .crawl import as_chain_file, trace
from .sources import sources
from .store import Store, now

FORMAT = {'bitcoin': re.compile(r'^(bc1[02-9ac-hj-np-z]{11,71}|[13][1-9A-HJ-NP-Za-km-z]{25,34})$'),
          'ethereum': re.compile(r'^0x[0-9a-fA-F]{40}$'), 'tron': re.compile(r'^T[1-9A-HJ-NP-Za-km-z]{33}$')}


class TraceIn(BaseModel):
    chain: str
    address: str
    hops: int = Field(3, ge=1, le=4)
    top: int = Field(5, ge=1, le=15)
    direction: str = Field('out', pattern='^(out|in|both)$')


def make_app(store=None, srcs=None, writer=None, token=None, out_dir=None, origin=None):
    app = FastAPI(title='Casefold crawler', version='0.1')
    store = store or Store(os.environ.get('CRAWLER_DB', 'crawler.sqlite'))
    srcs = srcs or sources()
    token = token if token is not None else os.environ.get('CRAWLER_TOKEN')
    out_dir = out_dir if out_dir is not None else os.environ.get('CRAWLER_OUT')
    origin = origin or os.environ.get('CRAWLER_ORIGIN')
    if writer is None and os.environ.get('NEO4J_URI'):
        from .graph import Neo4jWriter
        writer = Neo4jWriter()
    if origin:
        app.add_middleware(CORSMiddleware, allow_origins=[origin], allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'])
    pool = ThreadPoolExecutor(max_workers=2)
    lock = threading.Lock()      # one crawl at a time per store: the free tiers allow only a few calls a second

    def auth(authorization: str = Header('')):
        if not token:
            raise HTTPException(503, 'CRAWLER_TOKEN is not set on the server')
        if not secrets.compare_digest(authorization, f'Bearer {token}'):
            raise HTTPException(401, 'not authorised')

    def run(jid, p):
        store.db.execute("UPDATE job SET status='running' WHERE id=?", (jid,)); store.db.commit()
        try:
            with lock:
                r = trace(srcs[p.chain], store, p.address, p.hops, p.top, p.direction, log=lambda m: None)
            if writer:
                r['graph'] = writer.write(r)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
                f = os.path.join(out_dir, f"trace-{p.chain}-{p.address}.json")
                json.dump(as_chain_file(r), open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
            store.db.execute("UPDATE job SET status='done', done=?, result=? WHERE id=?", (now(), json.dumps(r), jid))
        except Exception as e:      # the job records what went wrong; the API stays up
            store.db.execute("UPDATE job SET status='failed', done=?, error=? WHERE id=?", (now(), str(e)[:500], jid))
        store.db.commit()

    @app.get('/health')
    def health():
        return {'ok': True, 'chains': sorted(srcs), 'store': store.stats(), 'neo4j': bool(writer)}

    @app.post('/trace', dependencies=[Depends(auth)])
    def start(p: TraceIn):
        if p.chain not in srcs:
            raise HTTPException(422, f'chain {p.chain} is not configured; configured: {", ".join(sorted(srcs))}')
        if p.chain in FORMAT and not FORMAT[p.chain].match(p.address):
            raise HTTPException(422, f'not a {p.chain} address')
        jid = uuid.uuid4().hex[:16]
        store.db.execute('INSERT INTO job VALUES (?,?,?,?,?,?,?,?,?)', (jid, p.chain, p.address, p.model_dump_json(), 'queued', now(), None, None, None)); store.db.commit()
        pool.submit(run, jid, p)
        return {'id': jid, 'status': 'queued'}

    @app.get('/trace/{jid}', dependencies=[Depends(auth)])
    def status(jid: str):
        r = store.db.execute('SELECT * FROM job WHERE id=?', (jid,)).fetchone()
        if not r:
            raise HTTPException(404, 'no such trace')
        out = {'id': r['id'], 'chain': r['chain'], 'address': r['address'], 'status': r['status'], 'created': r['created'], 'done': r['done']}
        if r['status'] == 'done':
            out['trace'] = json.loads(r['result'])
        if r['status'] == 'failed':
            out['error'] = r['error']
        return out

    app.state.pool = pool
    return app

