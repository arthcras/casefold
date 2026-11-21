"""The crawler's own store (SQLite): which addresses were fetched when, and every transfer it saw.

A later trace reuses what is fresh (max_age) and only asks the chain for the rest. The transfers keep their evidence:
chain, tx hash, time, block and the API they came from.
"""
import datetime, sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS fetched (chain TEXT, address TEXT, at TEXT, n INTEGER, PRIMARY KEY (chain, address));
CREATE TABLE IF NOT EXISTS transfer (chain TEXT, tx TEXT, time TEXT, block INTEGER, sender TEXT, receiver TEXT, amount REAL, asset TEXT, api TEXT, contract TEXT,
  PRIMARY KEY (chain, tx, sender, receiver, asset, amount));
CREATE INDEX IF NOT EXISTS t_from ON transfer (chain, sender);
CREATE INDEX IF NOT EXISTS t_to ON transfer (chain, receiver);
CREATE TABLE IF NOT EXISTS job (id TEXT PRIMARY KEY, chain TEXT, address TEXT, params TEXT, status TEXT, created TEXT, done TEXT, result TEXT, error TEXT);
"""


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class Store:
    def __init__(self, path=':memory:'):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def fresh(self, chain, address, max_age_hours):
        r = self.db.execute('SELECT at FROM fetched WHERE chain=? AND address=?', (chain, address)).fetchone()
        if not r:
            return False
        age = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(r['at'].replace('Z', '+00:00'))
        return age.total_seconds() < max_age_hours * 3600

    def save(self, chain, address, transfers):
        self.db.executemany('INSERT OR IGNORE INTO transfer VALUES (?,?,?,?,?,?,?,?,?,?)',
                            [(t['chain'], t['tx'], t['time'], t.get('block'), t['from'], t['to'], t['amount'], t['asset'], t['api'], t.get('contract')) for t in transfers if t.get('from') and t.get('to')])
        self.db.execute('INSERT OR REPLACE INTO fetched VALUES (?,?,?,?)', (chain, address, now(), len(transfers)))
        self.db.commit()

    def of(self, chain, address):
        rows = self.db.execute('SELECT * FROM transfer WHERE chain=? AND (sender=? OR receiver=?)', (chain, address, address)).fetchall()
        return [{'chain': r['chain'], 'tx': r['tx'], 'time': r['time'], 'block': r['block'], 'from': r['sender'], 'to': r['receiver'],
                 'amount': r['amount'], 'asset': r['asset'], 'api': r['api'], 'contract': r['contract']} for r in rows]

    def stats(self):
        return {'addresses': self.db.execute('SELECT count(*) FROM fetched').fetchone()[0], 'transfers': self.db.execute('SELECT count(*) FROM transfer').fetchone()[0]}
