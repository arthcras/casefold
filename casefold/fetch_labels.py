#!/usr/bin/env python3
"""Labels from the open eth-labels dataset (github.com/dawsbot/eth-labels, MIT; its labels come from the Etherscan label
cloud, so check the terms before commercial use) for the ethereum addresses in data/crypto/chain/.
Keeps only the addresses we traced, so the file stays small. Writes data/crypto/chain/labels_eth-labels.json.

  python3 casefold/fetch_labels.py [path/to/accounts.csv]     (default: download from GitHub)
"""
import csv, datetime, io, json, os, sys, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, 'data', 'crypto', 'chain')
URL = 'https://raw.githubusercontent.com/dawsbot/eth-labels/master/data/csv/accounts.csv'


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else URL
    text = open(src, encoding='utf-8').read() if os.path.exists(src) else urllib.request.urlopen(src, timeout=120).read().decode('utf-8')
    want = set()
    for f in os.listdir(D):
        if f.endswith('.json') and not f.startswith('labels'):
            for t in json.load(open(os.path.join(D, f), encoding='utf-8'))['transfers']:
                if t['chain'] == 'ethereum':
                    want |= {t['from'].lower(), t['to'].lower()}
    out = {}
    for r in csv.DictReader(io.StringIO(text)):
        a = r['address'].lower()
        if r['chainId'] == '1' and a in want:
            x = out.setdefault('ethereum:' + a, {'source': 'eth-labels (Etherscan label cloud)', 'tags': []})
            x['tags'].append({'field': r['label'], 'text': r['nameTag'] or r['label']})
    json.dump({'note': 'Ethereum address labels from the eth-labels dataset (MIT; labels from the Etherscan label cloud: check the terms before commercial use), only for the traced addresses.',
               'source': src if src.startswith('http') else 'local file', 'fetched': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
               'checked': len(want), 'labels': dict(sorted(out.items()))}, open(os.path.join(D, 'labels_eth-labels.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'eth-labels: {len(out)} of {len(want)} traced ethereum addresses labelled')


if __name__ == '__main__':
    main()
