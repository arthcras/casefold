"""Investigations on the server: one shared store for the back office, instead of each browser's own copy.

Every investigation is kept whole (the JSON the app works with) with a version number: a save names the version it
started from, and a save from an older version is refused (409), so two people never overwrite each other unnoticed.
Every change writes an event to an append-only audit trail (who, when, what, the SHA-256 of the saved document),
chained by hash: each event's hash covers the previous one, so a changed or removed event breaks the chain.
SQLite triggers refuse UPDATE and DELETE on the audit table. Deleting an investigation hides it; nothing is erased.

Who did it comes from the Cloudflare Access token (its e-mail), never from the request body.
"""
import hashlib, json, re

SCHEMA = """
CREATE TABLE IF NOT EXISTS case_doc (id TEXT PRIMARY KEY, name TEXT, status TEXT, version INTEGER, doc TEXT, sha256 TEXT,
  created TEXT, created_by TEXT, updated TEXT, updated_by TEXT, deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS case_event (n INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, at TEXT, by TEXT, action TEXT,
  version INTEGER, sha256 TEXT, note TEXT, prev TEXT, hash TEXT);
CREATE INDEX IF NOT EXISTS ce_case ON case_event (case_id);
CREATE TRIGGER IF NOT EXISTS ce_no_update BEFORE UPDATE ON case_event BEGIN SELECT RAISE(ABORT, 'the audit trail is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ce_no_delete BEFORE DELETE ON case_event BEGIN SELECT RAISE(ABORT, 'the audit trail is append-only'); END;
"""
ID = re.compile(r'^INV-[A-Za-z0-9_-]{1,40}$')
MAX = 8 * 1024 * 1024


def canon(doc):
    return json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def ev_hash(prev, e):
    return sha((prev or '') + canon({k: e[k] for k in ('case_id', 'at', 'by', 'action', 'version', 'sha256', 'note')}))


class Cases:
    def __init__(self, db, now):
        self.db, self.now = db, now
        db.executescript(SCHEMA)

    def _event(self, case_id, by, action, version, digest, note=''):
        last = self.db.execute('SELECT hash FROM case_event ORDER BY n DESC LIMIT 1').fetchone()
        e = {'case_id': case_id, 'at': self.now(), 'by': by, 'action': action, 'version': version, 'sha256': digest, 'note': note}
        prev = last['hash'] if last else ''
        self.db.execute('INSERT INTO case_event (case_id, at, by, action, version, sha256, note, prev, hash) VALUES (?,?,?,?,?,?,?,?,?)',
                        (case_id, e['at'], by, action, version, digest, note, prev, ev_hash(prev, e)))

    def list(self, full=False):
        rows = self.db.execute('SELECT * FROM case_doc WHERE deleted = 0 ORDER BY updated DESC').fetchall()
        return [self._row(r, full) for r in rows]

    def _row(self, r, full=True):
        out = {k: r[k] for k in ('id', 'name', 'status', 'version', 'sha256', 'created', 'created_by', 'updated', 'updated_by')}
        if full:
            out['doc'] = json.loads(r['doc'])
        return out

    def get(self, cid):
        r = self.db.execute('SELECT * FROM case_doc WHERE id = ? AND deleted = 0', (cid,)).fetchone()
        return self._row(r) if r else None

    def put(self, cid, doc, base, by):
        """Save; base is the version the change started from (0 for a new one). Returns (status, body)."""
        if not ID.match(cid) or not isinstance(doc, dict) or doc.get('id') != cid:
            return 422, {'detail': 'the id must look like INV-… and match the document'}
        text = canon(doc)
        if len(text.encode('utf-8')) > MAX:
            return 413, {'detail': 'the investigation is larger than 8 MB'}
        r = self.db.execute('SELECT * FROM case_doc WHERE id = ?', (cid,)).fetchone()
        if r and r['deleted']:
            return 410, {'detail': 'this investigation was deleted'}
        cur = r['version'] if r else 0
        if base != cur:
            return 409, {'detail': 'changed meanwhile', 'version': cur, 'updated_by': r['updated_by'] if r else None, 'updated': r['updated'] if r else None}
        digest, at, v = sha(text), self.now(), cur + 1
        if r and r['sha256'] == digest:
            return 200, self._row(r, False)
        if r:
            self.db.execute('UPDATE case_doc SET name=?, status=?, version=?, doc=?, sha256=?, updated=?, updated_by=? WHERE id=?',
                            (str(doc.get('name', ''))[:300], str(doc.get('status', '')), v, text, digest, at, by, cid))
        else:
            self.db.execute('INSERT INTO case_doc VALUES (?,?,?,?,?,?,?,?,?,?,0)',
                            (cid, str(doc.get('name', ''))[:300], str(doc.get('status', '')), v, text, digest, at, by, at, by))
        self._event(cid, by, 'update' if r else 'create', v, digest)
        self.db.commit()
        return 200, self._row(self.db.execute('SELECT * FROM case_doc WHERE id = ?', (cid,)).fetchone(), False)

    def delete(self, cid, base, by):
        r = self.db.execute('SELECT * FROM case_doc WHERE id = ? AND deleted = 0', (cid,)).fetchone()
        if not r:
            return 404, {'detail': 'no such investigation'}
        if base != r['version']:
            return 409, {'detail': 'changed meanwhile', 'version': r['version'], 'updated_by': r['updated_by'], 'updated': r['updated']}
        self.db.execute('UPDATE case_doc SET deleted = 1, updated = ?, updated_by = ? WHERE id = ?', (self.now(), by, cid))
        self._event(cid, by, 'delete', r['version'], r['sha256'], 'hidden from the list; the document and its history are kept')
        self.db.commit()
        return 200, {'id': cid, 'deleted': True}

    def audit(self, cid=None):
        """The events (of one investigation, or all) and whether the whole chain is intact."""
        allrows = self.db.execute('SELECT * FROM case_event ORDER BY n').fetchall()
        ok, prev = True, ''
        for e in allrows:
            if e['prev'] != prev or e['hash'] != ev_hash(prev, dict(e)):
                ok = False
                break
            prev = e['hash']
        ev = [{k: e[k] for k in ('n', 'at', 'by', 'action', 'version', 'sha256', 'note', 'hash')} | {'case_id': e['case_id']}
              for e in allrows if cid is None or e['case_id'] == cid]
        return {'chain_ok': ok, 'events': ev, 'head': prev}
