"""Chain sources for the crawler: one adapter per transaction model, not per chain.

  UtxoSource   Bitcoin (and Litecoin) via a mempool.space-style API      /api/address/<a>/txs[/chain/<last>]
  EvmSource    Ethereum and other EVM chains via Blockscout             /api/v2/addresses/<a>/token-transfers, /transactions
  TronSource   Tron via TronGrid                                        /v1/accounts/<a>/transactions/trc20, /transactions

Each returns transfers as dicts: chain, tx, time (ISO, UTC), block, from, to, amount, asset, contract (tokens), api. A token whose contract
is not the known USDT/USDC contract keeps its symbol with a * (a lookalike or spam token), as in fetch_chain.py.
Keys come from the environment (TRONGRID_API_KEY, ETHERSCAN_API_KEY): never from code, never from git.
"""
import datetime, json, os, time, urllib.parse, urllib.request

KNOWN = {'0xdac17f958d2ee523a2206206994597c13d831ec7': 'USDT', '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': 'USDC',
         'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t': 'USDT', 'TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8': 'USDC'}


def iso(ts):
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts.replace('+00:00', 'Z') if ts.endswith('+00:00') else ts if ts.endswith('Z') else ts + 'Z'
    return datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class Http:
    """GET with retries and a minimum interval per host (the free tiers allow a few calls per second)."""
    def __init__(self, interval=None, timeout=60):
        self.interval = interval or {}
        self.last = {}
        self.timeout = timeout
        self.calls = 0

    def get(self, url, headers=None, tries=4):
        host = urllib.parse.urlparse(url).netloc
        wait = self.interval.get(host, 0.35) - (time.monotonic() - self.last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        for i in range(tries):
            self.last[host] = time.monotonic(); self.calls += 1
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'casefold-crawler/1.0', 'Accept': 'application/json', **(headers or {})})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read())
            except Exception as e:
                code = getattr(e, 'code', None)
                if code in (400, 401, 403, 404) or i == tries - 1:
                    raise SourceError(f'{host}: {e}') from e
                time.sleep(2 + 3 * i if code != 429 else 10 + 10 * i)


class SourceError(Exception):
    pass


class UtxoSource:
    model = 'utxo'

    def __init__(self, chain='bitcoin', base='https://mempool.space/api', http=None, asset='BTC', decimals=8):
        self.chain, self.base, self.http, self.asset, self.dec = chain, base.rstrip('/'), http or Http(), asset, decimals

    def transfers(self, addr, limit=50):
        out, last, seen = [], None, 0
        while seen < limit:
            txs = self.http.get(f'{self.base}/address/{addr}/txs' + (f'/chain/{last}' if last else '')) or []
            if not txs:
                break
            for t in txs:
                seen += 1
                out += self._flows(addr, t)
            last = txs[-1]['txid']
            if len(txs) < 25:      # mempool pages hold 25 confirmed transactions
                break
        return out

    def _flows(self, addr, t):
        st = t.get('status') or {}
        when, block = iso(st.get('block_time')), st.get('block_height')
        ins = [v.get('prevout') or {} for v in t.get('vin', [])]
        in_addrs = [i.get('scriptpubkey_address') for i in ins if i.get('scriptpubkey_address')]
        row = lambda f, to, v: {'chain': self.chain, 'tx': t['txid'], 'time': when, 'block': block, 'from': f, 'to': to, 'amount': round(v / 10 ** self.dec, 8), 'asset': self.asset, 'api': self.base}
        if addr in in_addrs:       # the address pays: one flow per output to another address (change back to an input is left out)
            return [row(addr, o['scriptpubkey_address'], o['value']) for o in t.get('vout', []) if o.get('scriptpubkey_address') and o['scriptpubkey_address'] not in in_addrs]
        got = sum(o['value'] for o in t.get('vout', []) if o.get('scriptpubkey_address') == addr)
        return [row(in_addrs[0], addr, got)] if got and in_addrs else []


class EvmSource:
    model = 'evm'

    def __init__(self, chain='ethereum', base='https://eth.blockscout.com/api/v2', http=None, native='ETH', known=None):
        self.chain, self.base, self.http, self.native, self.known = chain, base.rstrip('/'), http or Http(), native, {**KNOWN, **(known or {})}

    def _pages(self, path, limit):
        items, params = [], {}
        while len(items) < limit:
            url = f'{self.base}{path}'
            if params:
                url += ('&' if '?' in path else '?') + urllib.parse.urlencode(params)
            r = self.http.get(url) or {}
            items += r.get('items') or []
            params = r.get('next_page_params')
            if not params:
                break
        return items[:limit]

    def transfers(self, addr, limit=50):
        out = []
        for x in self._pages(f'/addresses/{addr}/token-transfers?type=ERC-20', limit):
            tot, tok = x.get('total') or {}, x.get('token') or {}
            try:
                amt = int(tot.get('value') or 0) / 10 ** int(tot.get('decimals') or tok.get('decimals') or 18)
            except (TypeError, ValueError):
                continue
            c = (tok.get('address_hash') or tok.get('address') or '').lower()
            out.append({'chain': self.chain, 'tx': x.get('transaction_hash'), 'time': iso(x.get('timestamp')), 'block': x.get('block_number'),
                        'from': (x.get('from') or {}).get('hash'), 'to': (x.get('to') or {}).get('hash'), 'amount': round(amt, 8),
                        'asset': self.known.get(c) or (tok.get('symbol') or '?') + '*', 'contract': c or None, 'api': self.base})
        for x in self._pages(f'/addresses/{addr}/transactions', limit):
            v = int(x.get('value') or 0) / 1e18
            if v:
                out.append({'chain': self.chain, 'tx': x.get('hash'), 'time': iso(x.get('timestamp')), 'block': x.get('block_number') or x.get('block'),
                            'from': (x.get('from') or {}).get('hash'), 'to': (x.get('to') or {}).get('hash'), 'amount': round(v, 8), 'asset': self.native, 'api': self.base})
        return out


class TronSource:
    model = 'tron'

    def __init__(self, chain='tron', base='https://api.trongrid.io', http=None, key=None):
        self.chain, self.base, self.http = chain, base.rstrip('/'), http or Http(interval={'api.trongrid.io': 1.2})
        self.key = key if key is not None else os.environ.get('TRONGRID_API_KEY')
        if self.key and isinstance(self.http, Http):
            self.http.interval['api.trongrid.io'] = 0.12     # with a key: up to about 10 calls a second

    def _pages(self, path, limit):
        h = {'TRON-PRO-API-KEY': self.key} if self.key else None
        items, fp = [], None
        while len(items) < limit:
            q = f'limit={min(200, limit)}&only_confirmed=true' + (f'&fingerprint={urllib.parse.quote(fp)}' if fp else '')
            r = self.http.get(f'{self.base}{path}?{q}', headers=h) or {}
            items += r.get('data') or []
            fp = (r.get('meta') or {}).get('fingerprint')
            if not fp:
                break
        return items[:limit]

    def transfers(self, addr, limit=50):
        out = []
        for x in self._pages(f'/v1/accounts/{addr}/transactions/trc20', limit):
            ti = x.get('token_info') or {}
            try:
                amt = int(x.get('value') or 0) / 10 ** int(ti.get('decimals') or 6)
            except (TypeError, ValueError):
                continue
            out.append({'chain': self.chain, 'tx': x.get('transaction_id'), 'time': iso((x.get('block_timestamp') or 0) // 1000 or None), 'block': None,
                        'from': x.get('from'), 'to': x.get('to'), 'amount': round(amt, 8),
                        'asset': KNOWN.get(ti.get('address') or '') or (ti.get('symbol') or '?') + '*', 'contract': ti.get('address'), 'api': self.base})
        return out


def sources(http=None):
    """The chains of priority 1. Other EVM chains are an EvmSource with their own Blockscout base (see config)."""
    h = http or Http(interval={'api.trongrid.io': 1.2})
    return {'bitcoin': UtxoSource(http=h), 'ethereum': EvmSource(http=h), 'tron': TronSource(http=h)}


# EVM chains for phase 3: the same adapter, another Blockscout instance. Bases to be checked before use.
EVM_CHAINS = {'base': ('https://base.blockscout.com/api/v2', 'ETH'), 'optimism': ('https://optimism.blockscout.com/api/v2', 'ETH'),
              'arbitrum': ('https://arbitrum.blockscout.com/api/v2', 'ETH'), 'polygon': ('https://polygon.blockscout.com/api/v2', 'POL')}
