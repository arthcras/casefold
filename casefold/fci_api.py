"""A read-only /fci-api for the Hume workspace, on the Casefold crypto graph.

The Hume workspace (knode-platform, gatekeeper/hume/index.html) opened with ?blank=1 starts empty and asks
"this Neo4j" for nodes: search, expand a node, and fetch a subgraph. This server answers those three calls from
exports/hume/casefold-crypto.json (python3 casefold/export_hume.py), so the crypto register can be investigated in
Hume before it is loaded into Neo4j Community. The same three calls can later be answered from Neo4j with Cypher.

    python3 casefold/fci_api.py --hume ../knode-platform/gatekeeper/hume --port 8791
    open http://127.0.0.1:8791/   (Visualisations > New, then search e.g. Garantex)

Local use only: no login, read-only, binds to 127.0.0.1.
"""
import argparse
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT = os.path.join(ROOT, 'exports', 'hume', 'casefold-crypto.json')
MAX_EXPAND = 60


class Graph:
    def __init__(self, path):
        g = json.load(open(path))
        self.nodes = {n['id']: n for n in g['nodes']}
        self.rels = g['relationships']
        self.adj = {}
        for r in self.rels:
            self.adj.setdefault(r['start_id'], []).append(r)
            self.adj.setdefault(r['end_id'], []).append(r)
        self.text = {i: (i + ' ' + json.dumps(n['properties'], ensure_ascii=False)).lower() for i, n in self.nodes.items()}

    def search(self, q, limit):
        q = (q or '').strip().lower()
        if len(q) < 2:
            return []
        exact = [self.nodes[i] for i, t in self.text.items() if q == str(self.nodes[i]['properties'].get('display', '')).lower()]
        rest = [self.nodes[i] for i, t in self.text.items() if q in t and self.nodes[i] not in exact]
        rest.sort(key=lambda n: -len(self.adj.get(n['id'], [])))
        return (exact + rest)[:limit]

    def expand(self, i):
        rels = sorted(self.adj.get(i, []), key=lambda r: r['type'])[:MAX_EXPAND]
        ids = {i} | {r['start_id'] for r in rels} | {r['end_id'] for r in rels}
        return {'nodes': [self.nodes[x] for x in ids if x in self.nodes], 'relationships': rels}

    def subgraph(self, ids):
        ids = {i for i in ids if i in self.nodes}
        rels = [r for i in ids for r in self.adj.get(i, []) if r['start_id'] in ids and r['end_id'] in ids]
        uniq = {(r['start_id'], r['type'], r['end_id'], json.dumps(r['properties'], sort_keys=True)): r for r in rels}
        return {'nodes': [self.nodes[i] for i in ids], 'relationships': list(uniq.values())}


def handler(graph, hume_dir):
    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=hume_dir, **k)

        def log_message(self, *a):
            pass

        def _json(self, code, obj):
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            u = urlparse(self.path)
            p, q = u.path, parse_qs(u.query)
            if p == '/fci-api/graph/search':
                lim = max(1, min(int((q.get('limit') or ['12'])[0] or 12), 50))
                return self._json(200, graph.search((q.get('q') or [''])[0], lim))
            if p.startswith('/fci-api/graph/nodes/') and p.endswith('/expand'):
                i = unquote(p[len('/fci-api/graph/nodes/'):-len('/expand')])
                return self._json(200, graph.expand(i)) if i in graph.nodes else self._json(404, {'detail': 'unknown node'})
            if p.startswith('/fci-api/graph/nodes/'):
                i = unquote(p[len('/fci-api/graph/nodes/'):])
                return self._json(200, graph.nodes[i]) if i in graph.nodes else self._json(404, {'detail': 'unknown node'})
            if p == '/fci-api/orchestra/pipelines':
                return self._json(200, {'pipelines': []})
            if p.startswith('/fci-api/'):
                return self._json(200, [])
            if p == '/api/session':
                return self._json(200, {'gebruiker': 'local', 'tenant': 'casefold-crypto', 'tenants': ['casefold-crypto'], 'owner': False})
            if p.startswith('/api/'):
                return self._json(404, {'detail': 'not here'})
            if p in ('/', '/index.html'):
                if 'blank=1' not in u.query:
                    self.send_response(302)
                    self.send_header('Location', '/?blank=1&instance=casefold-crypto')
                    self.end_headers()
                    return
                return self._page()
            return super().do_GET()

        def _page(self):
            html = open(os.path.join(hume_dir, 'index.html'), encoding='utf-8').read()
            # Blank mode must not run the demo seed on the emptied graph (fixed here, in memory only).
            html = html.replace('if(!window.__HUME_LIVE__){\n  runAlerts(', 'if(!window.__HUME_LIVE__ && !window.__HUME_BLANK__){\n  runAlerts(', 1)
            data = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            n = int(self.headers.get('Content-Length') or 0)
            body = json.loads(self.rfile.read(n) or b'{}') if n else {}
            if self.path.startswith('/fci-api/graph/subgraph'):
                return self._json(200, graph.subgraph(body.get('ids') or []))
            return self._json(200, {})
    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hume', required=True, help='folder with the Hume index.html (knode-platform/gatekeeper/hume)')
    ap.add_argument('--port', type=int, default=8791)
    ap.add_argument('--export', default=EXPORT)
    a = ap.parse_args()
    if not os.path.exists(a.export):
        import subprocess, sys
        subprocess.run([sys.executable, os.path.join(ROOT, 'casefold', 'export_hume.py')], check=True)
    g = Graph(a.export)
    print(f'fci-api: {len(g.nodes)} nodes, {len(g.rels)} relationships. Open http://127.0.0.1:{a.port}/')
    ThreadingHTTPServer(('127.0.0.1', a.port), handler(g, os.path.abspath(a.hume))).serve_forever()


if __name__ == '__main__':
    main()
