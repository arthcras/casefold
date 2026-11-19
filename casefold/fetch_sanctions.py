#!/usr/bin/env python3
"""Fetch the sanctions lists and keep what crypto screening needs (needs internet; run by the sanctions workflow).

For every list: each listed person or entity with its list id, name, aliases, type and programmes, and every
crypto address the list gives for it (OFAC publishes these as "Digital Currency Address - <currency>").
Writes data/crypto/sanctions/<list>.json with the source URL, the download time and the sha256 of the file.

  python3 casefold/fetch_sanctions.py            all lists in data/crypto/sanctions_lists.json that have a "fetch" URL
  python3 casefold/fetch_sanctions.py LIST:ofac-sdn
"""
import datetime, hashlib, json, os, re, sys, urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, 'data', 'crypto', 'sanctions')
# strict shapes only, for lists that do not label crypto addresses: bech32 bitcoin, ethereum-style, tron
LOOSE = re.compile(r'\b(bc1[ac-hj-np-z02-9]{25,62}|0x[a-fA-F0-9]{40}|T[1-9A-HJ-NP-Za-km-z]{33})\b')


def local(tag):
    return tag.rsplit('}', 1)[-1]


def kids(e, name):
    return [c for c in e if local(c.tag) == name]


def kid(e, name):
    return next(iter(kids(e, name)), None)


def txt(e, name):
    c = kid(e, name)
    return (c.text or '').strip() if c is not None and c.text else ''


def chain_of(currency, address):
    c = currency.upper()
    if c in ('XBT', 'BTC') or address.startswith(('bc1', '1', '3')) and c == '':
        return 'bitcoin'
    if c in ('ETH', 'USDT', 'USDC', 'ETC', 'BSC', 'ARB') and address.startswith('0x'):
        return 'ethereum' if c != 'BSC' else 'bsc'
    if c in ('TRX',) or (c == 'USDT' and address.startswith('T')):
        return 'tron'
    if c == 'USDT':
        return 'bitcoin'   # USDT on Omni, a bitcoin address
    return {'XMR': 'monero', 'LTC': 'litecoin', 'ZEC': 'zcash', 'DASH': 'dash', 'BTG': 'bitcoin-gold', 'BCH': 'bitcoin-cash', 'XRP': 'xrp',
            'SOL': 'solana', 'XVG': 'verge'}.get(c, c.lower() or 'unknown')


def ofac(root):
    out = []
    for e in root.iter():
        if local(e.tag) != 'sdnEntry':
            continue
        name = ' '.join(x for x in (txt(e, 'firstName'), txt(e, 'lastName')) if x)
        akas = []
        al = kid(e, 'akaList')
        for a in (kids(al, 'aka') if al is not None else []):
            akas.append(' '.join(x for x in (txt(a, 'firstName'), txt(a, 'lastName')) if x))
        progs = [(p.text or '').strip() for p in (kids(kid(e, 'programList'), 'program') if kid(e, 'programList') is not None else [])]
        addrs = []
        il = kid(e, 'idList')
        for i in (kids(il, 'id') if il is not None else []):
            t = txt(i, 'idType')
            if t.lower().startswith('digital currency address'):
                cur = t.split('-')[-1].strip(); a = txt(i, 'idNumber')
                addrs.append({'currency': cur, 'chain': chain_of(cur, a), 'address': a})
        out.append({'id': 'OFAC:' + txt(e, 'uid'), 'name': name, 'aliases': akas[:8], 'type': txt(e, 'sdnType').lower(), 'programs': progs, 'addresses': addrs})
    return out


def un(root):
    out = []
    for e in root.iter():
        t = local(e.tag)
        if t not in ('INDIVIDUAL', 'ENTITY'):
            continue
        name = ' '.join(x for x in (txt(e, 'FIRST_NAME'), txt(e, 'SECOND_NAME'), txt(e, 'THIRD_NAME'), txt(e, 'FOURTH_NAME')) if x)
        akas = [txt(a, 'ALIAS_NAME') for a in e if local(a.tag) in ('INDIVIDUAL_ALIAS', 'ENTITY_ALIAS') and txt(a, 'ALIAS_NAME')]
        blob = ET.tostring(e, encoding='unicode')
        out.append({'id': 'UN:' + (txt(e, 'REFERENCE_NUMBER') or txt(e, 'DATAID')), 'name': name, 'aliases': akas[:8], 'type': 'individual' if t == 'INDIVIDUAL' else 'entity',
                    'programs': [txt(e, 'UN_LIST_TYPE')] if txt(e, 'UN_LIST_TYPE') else [], 'addresses': loose(blob)})
    return out


def eu(root):
    out = []
    for e in root.iter():
        if local(e.tag) != 'sanctionEntity':
            continue
        names = [a.get('wholeName') for a in e if local(a.tag) == 'nameAlias' and a.get('wholeName')]
        subj = kid(e, 'subjectType')
        reg = kid(e, 'regulation')
        blob = ET.tostring(e, encoding='unicode')
        out.append({'id': 'EU:' + (e.get('logicalId') or e.get('euReferenceNumber') or ''), 'name': names[0] if names else '', 'aliases': names[1:9],
                    'type': (subj.get('code') if subj is not None else '') or '', 'programs': [reg.get('programme')] if reg is not None and reg.get('programme') else [],
                    'addresses': loose(blob)})
    return out


def uk(root):
    out = []
    for e in root.iter():
        if local(e.tag) not in ('Designation', 'FinancialSanctionsTarget'):
            continue
        names = []
        for n in e.iter():
            if local(n.tag) in ('Name6', 'Name', 'WholeName', 'FullName') and (n.text or '').strip():
                names.append(n.text.strip())
        blob = ET.tostring(e, encoding='unicode')
        uid = txt(e, 'UniqueID') or txt(e, 'GroupID') or txt(e, 'OFSIGroupID')
        out.append({'id': 'UK:' + uid, 'name': names[0] if names else '', 'aliases': list(dict.fromkeys(names[1:]))[:8],
                    'type': (txt(e, 'IndividualEntityShip') or txt(e, 'GroupTypeDescription')).lower(), 'programs': [txt(e, 'RegimeName')] if txt(e, 'RegimeName') else [],
                    'addresses': loose(blob)})
    # the UK list repeats a target once per name: merge by id
    merged = {}
    for x in out:
        m = merged.setdefault(x['id'], x)
        if m is not x:
            m['aliases'] = list(dict.fromkeys(m['aliases'] + [x['name']] + x['aliases']))[:8]
            m['addresses'] += [a for a in x['addresses'] if a not in m['addresses']]
    return list(merged.values())


def loose(blob):
    seen, out = set(), []
    for a in LOOSE.findall(blob):
        if a not in seen:
            seen.add(a); out.append({'currency': '', 'chain': 'ethereum' if a.startswith('0x') else 'tron' if a.startswith('T') else 'bitcoin', 'address': a, 'unlabelled': True})
    return out


PARSERS = {'ofac': ofac, 'un': un, 'eu': eu, 'uk': uk}


def fetch(lst):
    last = None
    for url in lst['fetch']:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (casefold-sanctions)', 'Accept': 'application/xml,text/xml,*/*'})
            with urllib.request.urlopen(req, timeout=300) as r:
                data = r.read()
            if not data.lstrip().startswith(b'<'):
                raise ValueError(f'not XML ({len(data)} bytes)')
            return url, data
        except Exception as e:
            last = e; print(f"{lst['id']}: {url} failed: {e}", file=sys.stderr)
    raise RuntimeError(f"{lst['id']}: no source reachable ({last})")


def main():
    cfg = json.load(open(os.path.join(HERE, 'data', 'crypto', 'sanctions_lists.json'), encoding='utf-8'))
    want = set(a for a in sys.argv[1:] if a.startswith('LIST:'))
    os.makedirs(OUT, exist_ok=True)
    failed = 0
    for lst in cfg['lists']:
        if not lst.get('fetch') or (want and lst['id'] not in want):
            continue
        try:
            url, data = fetch(lst)
            entries = PARSERS[lst['parser']](ET.fromstring(data))
        except Exception as e:
            print(f"{lst['id']}: {e}", file=sys.stderr); failed += 1; continue
        entries = [x for x in entries if x['name']]
        n_addr = sum(len(x['addresses']) for x in entries)
        rec = {'list': lst['id'], 'name': lst['name'], 'source': url, 'fetched': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
               'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'entries_total': len(entries), 'addresses_total': n_addr,
               'entries': sorted(entries, key=lambda x: x['id'])}
        json.dump(rec, open(os.path.join(OUT, lst['id'].split(':', 1)[1] + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
        print(f"{lst['id']}: {len(entries)} entries, {n_addr} crypto addresses, from {url}")
    sys.exit(1 if failed == len([l for l in cfg['lists'] if l.get('fetch')]) else 0)


if __name__ == '__main__':
    main()
