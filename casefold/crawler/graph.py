"""Write a trace into Neo4j with the same Cypher the static build runs on Relate (build_crypto.LOAD, typologies.LOAD).

Connection from the environment: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (server secrets, never in git).
"""
import os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build_crypto, typologies  # noqa: E402

SENT = next(s for s in build_crypto.LOAD if s.startswith('UNWIND $t AS t'))
TRACED = next(s for s in build_crypto.LOAD if s.startswith('UNWIND $ts AS x'))
TT = [s for s in typologies.LOAD if '$tl' in s or '$te' in s]


def flows(transfers):
    """Transfers summed per (from, to, asset), as build_crypto.chain() does; lookalike tokens left out."""
    out = {}
    for t in transfers:
        if t['asset'].endswith('*') or not (0 < t['amount'] < 1e12):
            continue
        k = (t['chain'], t['from'], t['to'], t['asset'])
        x = out.setdefault(k, {'chain': t['chain'], 'from': t['from'], 'to': t['to'], 'from_key': f"{t['chain']}:{t['from']}", 'to_key': f"{t['chain']}:{t['to']}",
                               'asset': t['asset'], 'amount': 0.0, 'count': 0, 'first': t['time'], 'last': t['time'], 'tx': t['tx'], 'hop': t.get('hop', 1)})
        x['amount'] = round(x['amount'] + t['amount'], 8); x['count'] += 1; x['hop'] = min(x['hop'], t.get('hop', 1))
        if t['time'] and (not x['first'] or t['time'] < x['first']): x['first'] = t['time']
        if t['time'] and (not x['last'] or t['time'] > x['last']): x['last'] = t['time']; x['tx'] = t['tx']
    return list(out.values())


def statements(result, listed=(), labels=None, categories=None):
    """The (cypher, params) pairs for one trace: flows, traced addresses, then the typologies of these transfers."""
    out = [(SENT, {'t': flows(result['transfers'])}),
           (TRACED, {'ts': [{'key': a['key'], 'fetched': result['fetched_at'], 'hop': a['hop'], 'balance': None, 'asset': None, 'received': None, 'sent': None, 'tx_count': None} for a in result['addresses']]})]
    tt, tl, te, tg = typologies.detect(set(listed), labels or {}, categories or {}, transfers=result['transfers'])
    out += [(s, {'tl': tl, 'te': te}) for s in TT]
    return out


class Neo4jWriter:
    def __init__(self, uri=None, user=None, password=None):
        from neo4j import GraphDatabase
        self.driver = GraphDatabase.driver(uri or os.environ['NEO4J_URI'], auth=(user or os.environ.get('NEO4J_USER', 'neo4j'), password or os.environ['NEO4J_PASSWORD']))

    def context(self):
        """What the typology rules need from the graph: listed addresses and labelled ones with their category severity."""
        with self.driver.session() as s:
            listed = {r['k'] for r in s.run('MATCH (:SanctionsList)-[:LISTS]->(:Entity)-[:CONTROLS]->(a:Address) RETURN DISTINCT a.key AS k')}
            labels = {r['k']: r['c'] for r in s.run('MATCH (a:Address)-[:IN_CATEGORY]->(c:RiskCategory) RETURN a.key AS k, c.id AS c')}
            cats = {r['id']: r['sev'] for r in s.run('MATCH (c:RiskCategory) RETURN c.id AS id, c.severity AS sev')}
        return listed, labels, cats

    def write(self, result):
        listed, labels, cats = self.context()
        with self.driver.session() as s:
            for q, p in statements(result, listed, labels, cats):
                s.run(q, p).consume()
        return {'flows': len(flows(result['transfers']))}
