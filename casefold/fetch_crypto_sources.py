#!/usr/bin/env python3
"""Fetch the sources behind Casefold Crypto Intelligence and read them in (needs internet; run locally or in the
crypto-sources workflow):

  1. the decision documents of the Dutch crypto cases (data/crypto/decisions.json): pdftotext, then every citation of
     an article ("artikel 23b, eerste en tweede lid, ... van de Wwft") with the sentence it stands in, the page and the
     sha256 of the document -> data/crypto/decision_citations.json (the decisions themselves are not committed);
  2. MiCA, the TFR and DAC8 from EUR-Lex, Dutch and English, read in article by article with law_ingest.py
     -> laws/<law>@<version>-<lang>.rl and .json.

  python3 casefold/fetch_crypto_sources.py               both
  python3 casefold/fetch_crypto_sources.py --decisions   only 1
  python3 casefold/fetch_crypto_sources.py --laws        only 2
"""
import hashlib, json, os, re, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, 'laws', 'sources')
LAWNAMES = {'wwft': 'NL:wwft', 'wet ter voorkoming van witwassen en financieren van terrorisme': 'NL:wwft', 'sanctiewet 1977': 'NL:sw1977',
            'awb': 'NL:awb', 'algemene wet bestuursrecht': 'NL:awb', 'micar': 'NL:mica', 'mica': 'NL:mica', 'tfr': 'NL:tfr',
            'besluit bestuurlijke boetes financiële sector': 'NL:bbbfs', 'wft': 'NL:wft'}
LAWS_RE = r'(Wwft|Wet ter voorkoming van witwassen en financieren van terrorisme|Sanctiewet 1977|Awb|Algemene wet bestuursrecht|MiCAR|MiCA|TFR|Wft)'
NUM = r'\d+(?::\d+)?[a-z]{0,2}'
# a run of article references ending in the law they belong to: "artikel 23b, eerste en tweede lid, en artikel 23c, derde lid, van de Wwft"
CITE = re.compile(r'\b(artikel(?:en)?\s+' + NUM + r'(?:(?!\bartikel)[^.;]){0,70}?(?:\s*,?\s*(?:en|of)\s+(?:artikel\s+)?' + NUM + r'(?:(?!\bartikel)[^.;]){0,70}?)*)\s(?:van\s+de\s+|van\s+het\s+)?\b' + LAWS_RE + r'\b', re.I)
ONE = re.compile(r'(?:artikel(?:en)?\s+|(?:en|of)\s+(?:artikel\s+)?)(' + NUM + r')((?:(?!\bartikel\b|\b(?:en|of)\s+(?:artikel\s+)?\d)[^.;])*)', re.I)
ORD = {'eerste': '1', 'tweede': '2', 'derde': '3', 'vierde': '4', 'vijfde': '5', 'zesde': '6', 'zevende': '7', 'achtste': '8', 'negende': '9', 'tiende': '10'}


def get(url, path, accept=None, lang=None):
    h = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) casefold-crypto-sources', 'Accept': accept or '*/*'}
    if lang:
        h['Accept-Language'] = lang
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=180) as r, open(path, 'wb') as f:
        f.write(r.read())
    data = open(path, 'rb').read()
    if len(data) < 2000 or not data.startswith(b'%PDF'):
        raise ValueError(f'not a PDF ({len(data)} bytes: {data[:60]!r})')
    return hashlib.sha256(data).hexdigest()


def pages(pdf):
    out = subprocess.run(['pdftotext', '-enc', 'UTF-8', '-layout', pdf, '-'], capture_output=True, text=True).stdout
    return out.split('\f')


def lids_of(t):
    w = re.findall(r'\b(eerste|tweede|derde|vierde|vijfde|zesde|zevende|achtste|negende|tiende)\b', t or '')
    return {ORD[x] for x in w} | set(re.findall(r'\blid\s+(\d+)', t or ''))


def parse(flat):
    """[(law, art, lids, start, end)] for every article reference in a text."""
    out = []
    for m in CITE.finditer(flat):
        law = LAWNAMES.get(m.group(2).lower(), m.group(2))
        for o in ONE.finditer(m.group(1)):
            out.append((law, o.group(1).lower(), lids_of(o.group(2)), m.start(), m.end()))
    return out


def citations(pdf):
    found = {}
    for n, page in enumerate(pages(pdf), 1):
        flat = re.sub(r'\s+', ' ', page)
        for law, art, lids, a, b in parse(flat):
            f = found.setdefault((law, art), {'law': law, 'art': art, 'lids': set(), 'count': 0, 'first_page': n, 'example': ''})
            f['lids'] |= lids; f['count'] += 1
            if not f['example']:
                f['example'] = flat[max(0, a - 100):b + 40].strip()
    return sorted(({**v, 'lids': sorted(v['lids'], key=lambda x: (len(x), x))} for v in found.values()), key=lambda v: (-v['count'], v['law'], v['art']))


def decisions(cfg):
    os.makedirs(os.path.join(SRC, 'decisions'), exist_ok=True)
    out = []
    for d in cfg['decisions']:
        path = os.path.join(SRC, 'decisions', d['url'].rsplit('/', 1)[1])
        try:
            h = get(d['url'], path)
        except Exception as e:
            print(f"{d['case']}: could not download {d['url']} ({e})", file=sys.stderr); out.append({**d, 'error': str(e)}); continue
        cites = citations(path)
        print(f"{d['case']}: {len(pages(path))} pages, sha256 {h[:12]}, {len(cites)} articles cited")
        out.append({**d, 'sha256': h, 'pages': len(pages(path)), 'citations': cites})
    json.dump({'note': 'Articles cited in each decision, read with pdftotext by casefold/fetch_crypto_sources.py. count = how often the decision cites it; '
                       'example = the words around the first citation. Which of them the decision finds violated is set in data/crypto/cases.json.',
               'decisions': out}, open(os.path.join(HERE, 'data', 'crypto', 'decision_citations.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def laws(cfg):
    """EUR-Lex first; then the Publications Office (Cellar), which serves the same official PDF by content negotiation."""
    os.makedirs(SRC, exist_ok=True)
    for l in cfg['laws']:
        for lang in ('nl', 'en'):
            path = os.path.join(SRC, f"{l['stem']}-{lang}.pdf")
            tries = [(f"https://eur-lex.europa.eu/legal-content/{lang.upper()}/TXT/PDF/?uri=CELEX:{l['celex']}", 'application/pdf', None)]
            for t in ('application/pdf;type=pdfa2a', 'application/pdf;type=pdfa1a', 'application/pdf;type=pdf1x', 'application/pdf'):
                tries.append((f"https://publications.europa.eu/resource/celex/{l['celex']}", t, {'nl': 'nld', 'en': 'eng'}[lang]))
            h = None
            for url, acc, lg in tries:
                try:
                    h = get(url, path, acc, lg)
                    print(f"{l['law']} ({lang}): {url} [{acc}] sha256 {h[:12]}")
                    break
                except Exception as e:
                    print(f"{l['law']} ({lang}): {url} [{acc}] failed: {e}", file=sys.stderr)
            if h:
                subprocess.run([sys.executable, os.path.join(HERE, 'casefold', 'law_ingest.py'), path, '--law', l['law'], '--version', l['version'], '--lang', lang,
                                '--title', l['title'][lang], '--url', l['url']], check=True)


if __name__ == '__main__':
    cfg = json.load(open(os.path.join(HERE, 'data', 'crypto', 'decisions.json'), encoding='utf-8'))
    if '--laws' not in sys.argv:
        decisions(cfg)
    if '--decisions' not in sys.argv:
        laws(cfg)
