#!/usr/bin/env python3
"""Write a change set from the back office (Data, casefold-changes/1) into data/crypto/.

  python3 casefold/apply_changes.py casefold-changes-2026-11-20.json            check and write
  python3 casefold/apply_changes.py casefold-changes-2026-11-20.json --dry-run  only show what would change

The file is {format, sealed, sha256}: `sealed` is the JSON the back office sealed. The SHA-256 is computed again; a
changed file is refused. Only confirmed changes are in a change set (proposer and reviewer are different people).
Each change is an upsert (fields merged into the record, other fields kept) or a delete, by key, in the file and path
of its kind. Afterwards: python3 casefold/build_crypto.py --export, then commit data/crypto and web/data.
"""
import hashlib, json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, 'data', 'crypto')
# kind -> (file, list in the file, key of a record); nested kinds live inside a jurisdiction
KINDS = {'case': ('cases.json', 'cases', lambda r: r['id']),
         'jurisdiction': ('jurisdictions.json', 'jurisdictions', lambda r: r['code']),
         'regulator': ('jurisdictions.json', 'regulators', lambda r: r['id']),
         'law': ('jurisdictions.json', 'laws', lambda r: r['id']),
         'article': ('articles.json', 'articles', lambda r: f"{r['law']}:{r['art']}"),
         'category': ('risk_categories.json', 'categories', lambda r: r['id']),
         'list': ('sanctions_lists.json', 'lists', lambda r: r['id']),
         'label': ('labels_analyst.json', 'labels', lambda r: r['key']),
         'trace': ('chain_seeds.json', 'entities', None)}
NESTED = {'regulator', 'law'}


def read(path):
    if not os.path.exists(path):
        return {'note': 'Wallet labels set by Casefold analysts in the back office (four eyes). They win over explorer and dataset labels.', 'labels': []}
    return json.load(open(path, encoding='utf-8'))


def apply(change, files, log):
    kind, op, key, rec = change['type'], change['op'], change['key'], change.get('record') or {}
    if kind not in KINDS:
        raise ValueError(f'unknown kind {kind}')
    fname, lst, keyf = KINDS[kind]
    doc = files.setdefault(fname, read(os.path.join(DATA, fname)))
    if kind == 'trace':
        ents = doc[lst]
        if op == 'delete':
            if key in ents:
                ents.remove(key); log.append(f'trace queue: - {key}')
        elif key not in ents:
            ents.append(key); log.append(f'trace queue: + {key}')
        return
    if kind in NESTED:
        code, key = key.split('|', 1)
        j = next((x for x in doc['jurisdictions'] if x['code'] == code), None)
        if j is None:
            raise ValueError(f'{kind} {key}: country {code} not in jurisdictions.json')
        items = j.setdefault(lst, [])
        rec = {k: v for k, v in rec.items() if k != 'jurisdiction'}
        where = f'{kind} {code}/{key}'
    else:
        items = doc[lst]
        where = f'{kind} {key}'
    i = next((n for n, x in enumerate(items) if keyf(x) == key), None)
    if op == 'delete':
        if i is not None:
            items.pop(i); log.append(f'{where}: deleted')
        return
    if kind == 'label':
        rec = {**rec, 'source': 'Casefold analyst', 'by': change.get('proposed_by'), 'confirmed_by': change.get('confirmed_by'), 'at': change.get('confirmed_at')}
    if i is None:
        if kind == 'jurisdiction':
            rec = {'regulators': [], 'laws': [], **rec}
        items.append(rec); log.append(f'{where}: new')
    else:
        rec = {k: v for k, v in rec.items() if k in items[i] or v not in ('', None, [])}   # no empty field where there was none
        changed = [k for k, v in rec.items() if items[i].get(k) != v]
        items[i] = {**items[i], **rec}
        log.append(f"{where}: {', '.join(changed) or 'no change'}")


def main(path, dry):
    f = json.load(open(path, encoding='utf-8'))
    if f.get('format') != 'casefold-changes/1' or not isinstance(f.get('sealed'), str):
        sys.exit('not a Casefold change set (casefold-changes/1)')
    if hashlib.sha256(f['sealed'].encode('utf-8')).hexdigest() != f.get('sha256'):
        sys.exit('the seal does not match: the change set was changed after the back office sealed it')
    body = json.loads(f['sealed'])
    files, log = {}, []
    for c in body['changes']:
        if not c.get('confirmed_by') or str(c.get('confirmed_by')).strip().lower() == str(c.get('proposed_by')).strip().lower():
            sys.exit(f"{c['type']} {c['key']}: not confirmed by a second person")
        apply(c, files, log)
    print(f"change set of {body['exported_at'][:16]} by {body['exported_by']}, sha256 {f['sha256'][:16]}…: {len(body['changes'])} changes")
    for x in log:
        print('  ' + x)
    if dry:
        print('dry run: nothing written'); return
    for fname, doc in files.items():
        json.dump(doc, open(os.path.join(DATA, fname), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        open(os.path.join(DATA, fname), 'a', encoding='utf-8').write('\n')
        print('written: data/crypto/' + fname)
    print('next: python3 casefold/build_crypto.py --export')


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if len(a) != 1:
        sys.exit(__doc__)
    main(a[0], '--dry-run' in sys.argv)
