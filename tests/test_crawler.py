#!/usr/bin/env python3
"""Crawler tests without internet: the sources get answers in the APIs' own formats (TronGrid, Blockscout, mempool.space)
from a fake HTTP client. A live run is the crawler workflow (.github/workflows/crawler.yml)."""
import json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from casefold.crawler.sources import UtxoSource, EvmSource, TronSource  # noqa: E402
from casefold.crawler.store import Store  # noqa: E402
from casefold.crawler.crawl import trace, as_chain_file  # noqa: E402
from casefold.crawler import graph  # noqa: E402

USDT_T = 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t'
A, B, C, D, E = ('T' + c * 33 for c in 'ABCDE')


class FakeHttp:
    def __init__(self, routes):
        self.routes, self.calls, self.seen = routes, 0, []

    def get(self, url, headers=None, tries=4):
        self.calls += 1; self.seen.append(url)
        for k in sorted(self.routes, key=len, reverse=True):
            if k in url:
                return self.routes[k]
        return {'data': []} if 'trongrid' in url else {'items': []} if 'blockscout' in url else []


def trc(tx, fr, to, v, ts, contract=USDT_T, sym='USDT'):
    return {'transaction_id': tx, 'from': fr, 'to': to, 'value': str(int(v * 1e6)), 'block_timestamp': ts * 1000,
            'token_info': {'address': contract, 'symbol': sym, 'decimals': 6}}


def tron_routes():
    t0 = 1_760_000_000
    return {
        f'/v1/accounts/{A}/transactions/trc20': {'data': [trc('t1', A, B, 9000, t0), trc('t2', A, C, 500, t0 + 60), trc('t3', D, A, 9500, t0 - 3600),
                                                          trc('t4', A, E, 1, t0, contract='TFake', sym='USDT')], 'meta': {}},
        f'/v1/accounts/{B}/transactions/trc20': {'data': [trc('t1', A, B, 9000, t0), trc('t5', B, D, 8800, t0 + 7200)], 'meta': {}},
        f'/v1/accounts/{C}/transactions/trc20': {'data': [trc('t2', A, C, 500, t0 + 60)], 'meta': {}},
    }


def test_tron_trace():
    h = FakeHttp(tron_routes()); src = TronSource(http=h, key=''); st = Store()
    r = trace(src, st, A, hops=2, top=2, log=lambda m: None)
    keys = [x['key'] for x in r['addresses']]
    assert keys[0] == f'tron:{A}' and f'tron:{B}' in keys and f'tron:{C}' in keys, keys
    assert f'tron:{E}' not in keys, 'a lookalike token is never followed'
    assert any(t['asset'] == 'USDT*' for t in r['transfers']), 'the lookalike is kept as evidence'
    assert all(t['time'].endswith('Z') for t in r['transfers'])
    n = h.calls
    trace(src, st, A, hops=2, top=2, log=lambda m: None)
    assert h.calls == n, 'a fresh address is not fetched again'
    f = as_chain_file(r)
    assert f['entity'] == f'TRACE:tron:{A}' and {'hop', 'chain', 'tx', 'time', 'from', 'to', 'amount', 'asset', 'api'} <= set(f['transfers'][0])
    print('  ok   tron: 2 hops, widest flows followed, lookalike kept not followed, cache reused, chain-file format')
    return r


def test_backward():
    src = TronSource(http=FakeHttp(tron_routes()), key='')
    r = trace(src, Store(), A, hops=1, top=3, direction='in', log=lambda m: None)
    assert [x['key'] for x in r['addresses']] == [f'tron:{A}', f'tron:{D}']
    print('  ok   backward: follows where the money came from')


def test_evm():
    a, b = '0x' + 'a' * 40, '0x' + 'b' * 40
    page1 = {'items': [{'transaction_hash': '0x1', 'timestamp': '2026-01-02T03:04:05.000000Z', 'block_number': 10, 'from': {'hash': a}, 'to': {'hash': b},
                        'total': {'value': '2500000000', 'decimals': '6'}, 'token': {'address_hash': '0xdAC17F958D2ee523a2206206994597C13D831ec7', 'symbol': 'USDT'}}],
             'next_page_params': {'block_number': 9, 'index': 1}}
    page2 = {'items': [{'transaction_hash': '0x2', 'timestamp': '2026-01-01T00:00:00Z', 'block_number': 9, 'from': {'hash': b}, 'to': {'hash': a},
                        'total': {'value': '1000000000000000000', 'decimals': '18'}, 'token': {'address_hash': '0x' + 'c' * 40, 'symbol': 'USDT'}}], 'next_page_params': None}
    h = FakeHttp({f'/addresses/{a}/token-transfers?type=ERC-20&block_number=9': page2, f'/addresses/{a}/token-transfers?type=ERC-20': page1,
                  f'/addresses/{a}/transactions': {'items': [{'hash': '0x3', 'timestamp': '2026-01-03T00:00:00Z', 'from': {'hash': a}, 'to': {'hash': b}, 'value': str(3 * 10 ** 18)}]}})
    ts = EvmSource(http=h).transfers(a, 50)
    assert [(t['tx'], t['asset'], t['amount']) for t in ts] == [('0x1', 'USDT', 2500.0), ('0x2', 'USDT*', 1.0), ('0x3', 'ETH', 3.0)], ts
    assert any('block_number=9' in u for u in h.seen), 'second page fetched'
    print('  ok   ethereum: known USDT contract, lookalike marked, native ETH, pages followed')


def test_utxo():
    x, y, z = 'bc1q' + 'x' * 38, 'bc1q' + 'y' * 38, 'bc1q' + 'z' * 38
    txs = [{'txid': 'b1', 'status': {'block_time': 1_700_000_000, 'block_height': 800000}, 'vin': [{'prevout': {'scriptpubkey_address': x, 'value': 100000000}}],
            'vout': [{'scriptpubkey_address': y, 'value': 90000000}, {'scriptpubkey_address': x, 'value': 9990000}]},
           {'txid': 'b2', 'status': {'block_time': 1_699_000_000}, 'vin': [{'prevout': {'scriptpubkey_address': z}}], 'vout': [{'scriptpubkey_address': x, 'value': 5000000}]}]
    ts = UtxoSource(http=FakeHttp({f'/address/{x}/txs': txs})).transfers(x, 50)
    assert [(t['from'], t['to'], t['amount']) for t in ts] == [(x, y, 0.9), (z, x, 0.05)], ts
    print('  ok   bitcoin: outputs to others (change left out), and received value')


def test_graph_statements(r):
    st = graph.statements(r, listed={f'tron:{D}'}, labels={}, categories={})
    names = [q.split('\n')[0][:30] for q, p in st]
    t = st[0][1]['t']
    assert any(f['from_key'] == f'tron:{A}' and f['to_key'] == f'tron:{B}' and f['amount'] == 9000 for f in t)
    assert not any(f['asset'].endswith('*') for f in t), 'lookalikes stay out of the graph'
    te = next(p for q, p in st if '$te' in q)['te']
    assert any('TT-LISTED' in x['typologies'] for x in te), 'transfer with a listed wallet labelled'
    assert any('TT-PASS' in x['typologies'] for x in te), 'B passed 8,800 of 9,000 on within 2 hours'
    print(f'  ok   graph: {len(st)} statements, the same Cypher as the build ({names[0]}…), typologies on the new transfers')


def test_api():
    from fastapi.testclient import TestClient
    from casefold.crawler.api import make_app
    app = make_app(store=Store(), srcs={'tron': TronSource(http=FakeHttp(tron_routes()), key='')}, writer=None, token='s3cret', out_dir='')
    c = TestClient(app)
    assert c.get('/health').json()['chains'] == ['tron']
    assert c.post('/trace', json={'chain': 'tron', 'address': A}).status_code == 401
    H = {'Authorization': 'Bearer s3cret'}
    assert c.post('/trace', json={'chain': 'tron', 'address': '0x12'}, headers=H).status_code == 422
    assert c.post('/trace', json={'chain': 'solana', 'address': A}, headers=H).status_code == 422
    jid = c.post('/trace', json={'chain': 'tron', 'address': A, 'hops': 1}, headers=H).json()['id']
    app.state.pool.shutdown(wait=True)
    r = c.get(f'/trace/{jid}', headers=H).json()
    assert r['status'] == 'done' and len(r['trace']['transfers']) >= 3, r
    assert set(r['trace']['typologies']) == {'tl', 'te'}, r['trace'].keys()
    assert c.get('/access/verify').status_code == 401, 'back office closed without Access settings'
    assert c.get('/access/verify', headers={'Cf-Access-Jwt-Assertion': 'x.y.z'}).status_code == 401
    print('  ok   api: token required, address and chain checked, a job runs and returns its trace; back office closed without Access')


def test_access_jwt():
    import jwt, time
    from cryptography.hazmat.primitives.asymmetric import rsa
    from fastapi.testclient import TestClient
    from casefold.crawler import api as A
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    os.environ['CF_ACCESS_TEAM'], os.environ['CF_ACCESS_AUD'] = 'team', 'aud123'   # the team name alone is completed
    try:
        app = A.make_app(store=Store(), srcs={}, writer=None, token='t', out_dir='')
    finally:
        del os.environ['CF_ACCESS_TEAM'], os.environ['CF_ACCESS_AUD']
    class K:  # stands in for the Access certificate endpoint
        def get_signing_key_from_jwt(self, t):
            return type('S', (), {'key': k.public_key()})()
    import jwt as J
    orig = J.PyJWKClient
    J.PyJWKClient = lambda *a, **kw: K()
    try:
        c = TestClient(app)
        ok = jwt.encode({'aud': 'aud123', 'iss': 'https://team.cloudflareaccess.com', 'email': 'a@b.c', 'exp': int(time.time()) + 60}, k, algorithm='RS256')
        bad = jwt.encode({'aud': 'other', 'iss': 'https://team.cloudflareaccess.com', 'exp': int(time.time()) + 60}, k, algorithm='RS256')
        r = c.get('/access/verify', headers={'Cf-Access-Jwt-Assertion': ok})
        assert r.status_code == 204 and r.headers['x-access-email'] == 'a@b.c', r.status_code
        assert c.get('/access/verify', headers={'Cf-Access-Jwt-Assertion': bad}).status_code == 401
    finally:
        J.PyJWKClient = orig
    print('  ok   access: a valid Cloudflare Access token passes, another audience is refused')


def test_poisoning():
    import typologies
    V, C, L = 'TEANdtCWWT2ojgHeTG35L4yhH37SnJG7BD', 'TNgj9egxAAAAAAAAAAAAAAAAAAAAA3idTky', 'TNgvj6UpBBBBBBBBBBBBBBBBBBBBB3idTky'
    tr = [{'chain': 'tron', 'from': C, 'to': V, 'asset': 'USDT', 'amount': 500000, 'time': '2025-03-20T10:00:00', 'tx': 'a'},
          {'chain': 'tron', 'from': L, 'to': V, 'asset': 'USDT', 'amount': 0.236, 'time': '2025-03-21T10:00:00', 'tx': 'b'},
          {'chain': 'tron', 'from': V, 'to': 'TXrealCounterpartyZZZZZZZZZZZZZZZZ', 'asset': 'USDT', 'amount': 2000, 'time': '2025-03-22T10:00:00', 'tx': 'c'}]
    _, tl, te, _ = typologies.detect(set(), {}, {}, transfers=tr)
    got = {(x['key'], x['typology']) for x in tl}
    assert ('tron:' + L, 'TT-POISON') in got and ('tron:' + C, 'TT-POISON') not in got and ('tron:' + V, 'TT-POISON') not in got, got
    assert not any('TT-ROUND' in x['typologies'] or 'TT-PASS' in x['typologies'] for x in te if x['from_key'] == 'tron:' + L), te
    _, tl, _, _ = typologies.detect(set(), {}, {}, transfers=tr + [{'chain': 'tron', 'from': V, 'to': L, 'asset': 'USDT', 'amount': 1000, 'time': '2025-03-23T10:00:00', 'tx': 'd'}])
    assert any(x['key'] == 'tron:' + V and x['typology'] == 'TT-POISON' and 'may have worked' in x['evidence'] for x in tl), tl
    print('  ok   poisoning: dust from a lookalike of a real counterparty is flagged; dust is no pass-through or round trip; paying the lookalike is flagged')


def test_cases():
    import jwt, time
    from cryptography.hazmat.primitives.asymmetric import rsa
    from fastapi.testclient import TestClient
    from casefold.crawler import api as A
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    os.environ['CF_ACCESS_TEAM'], os.environ['CF_ACCESS_AUD'] = 'team', 'aud123'
    try:
        st = Store()
        app = A.make_app(store=st, srcs={}, writer=None, token='t', out_dir='')
    finally:
        del os.environ['CF_ACCESS_TEAM'], os.environ['CF_ACCESS_AUD']
    class K:
        def get_signing_key_from_jwt(self, t):
            return type('S', (), {'key': k.public_key()})()
    import jwt as J
    orig = J.PyJWKClient
    J.PyJWKClient = lambda *a, **kw: K()
    tok = lambda e: jwt.encode({'aud': 'aud123', 'iss': 'https://team.cloudflareaccess.com', 'email': e, 'exp': int(time.time()) + 60}, k, algorithm='RS256')
    try:
        c = TestClient(app)
        H1 = {'Authorization': 'Bearer t', 'Cf-Access-Jwt-Assertion': tok('Ann@X.com')}
        H2 = {'Authorization': 'Bearer t', 'Cf-Access-Jwt-Assertion': tok('bob@x.com')}
        doc = {'id': 'INV-abc', 'name': 'Wallet T…', 'status': 'open', 'items': [], 'log': []}
        assert c.get('/cases', headers={'Authorization': 'Bearer t'}).status_code == 401, 'Access token required'
        assert c.get('/cases', headers={'Cf-Access-Jwt-Assertion': tok('a@x.com')}).status_code == 401, 'server token required'
        assert c.put('/cases/INV-abc', json={'doc': {**doc, 'id': 'INV-other'}, 'version': 0}, headers=H1).status_code == 422
        r = c.put('/cases/INV-abc', json={'doc': doc, 'version': 0}, headers=H1).json()
        assert r['version'] == 1 and r['created_by'] == 'ann@x.com', r
        assert c.put('/cases/INV-abc', json={'doc': doc, 'version': 1}, headers=H2).json()['version'] == 1, 'unchanged: no new version'
        r = c.put('/cases/INV-abc', json={'doc': {**doc, 'status': 'review'}, 'version': 1}, headers=H2).json()
        assert r['version'] == 2 and r['updated_by'] == 'bob@x.com'
        r = c.put('/cases/INV-abc', json={'doc': {**doc, 'name': 'late'}, 'version': 1}, headers=H1)
        assert r.status_code == 409 and r.json()['detail']['updated_by'] == 'bob@x.com', r.text
        L = c.get('/cases?full=1', headers=H1).json()
        assert L['me'] == 'ann@x.com' and L['cases'][0]['doc']['status'] == 'review'
        assert c.delete('/cases/INV-abc?version=1', headers=H1).status_code == 409
        assert c.delete('/cases/INV-abc?version=2', headers=H1).status_code == 200
        assert c.get('/cases', headers=H1).json()['cases'] == [] and c.get('/cases/INV-abc', headers=H1).status_code == 404
        assert c.put('/cases/INV-abc', json={'doc': doc, 'version': 2}, headers=H1).status_code == 410
        a = c.get('/cases/INV-abc/audit', headers=H1).json()
        assert a['chain_ok'] and [e['action'] for e in a['events']] == ['create', 'update', 'delete'], a
        assert [e['by'] for e in a['events']] == ['ann@x.com', 'bob@x.com', 'ann@x.com']
        try:
            st.db.execute("UPDATE case_event SET by = 'x'"); raise AssertionError('audit trail changed')
        except Exception as e:
            assert 'append-only' in str(e), e
        st.db.execute('DROP TRIGGER ce_no_update'); st.db.execute("UPDATE case_event SET by = 'mallory' WHERE n = 2")
        assert not c.get('/cases/INV-abc/audit', headers=H1).json()['chain_ok'], 'a changed event breaks the chain'
    finally:
        J.PyJWKClient = orig
    print('  ok   cases: server token and Access both required; versions refuse a stale save (409); delete hides; audit trail append-only and hash-chained')


if __name__ == '__main__':
    r = test_tron_trace(); test_backward(); test_evm(); test_utxo(); test_graph_statements(r); test_api(); test_access_jwt(); test_poisoning(); test_cases()
    print('crawler: all pass')
