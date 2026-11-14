#!/usr/bin/env python3
"""Download the official law texts into laws/sources/ (run this on your own machine; it needs internet access).

    python3 casefold/law_fetch.py                 # all sources below, the version valid today
    python3 casefold/law_fetch.py --date 2026-01-01

Dutch law: the PDF print of wetten.overheid.nl for the version valid on --date.
EU law: the PDF of EUR-Lex, in Dutch and in English (the official English text).
Then read each file in with casefold/law_ingest.py (pdftotext, or tesseract with --ocr) and run casefold/build_duties.py.
"""
import argparse, datetime, hashlib, os, sys, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NL = {   # law id: (BWB id, file stem, title)
    'NL:wwft': ('BWBR0024282', 'wwft', 'Wet ter voorkoming van witwassen en financieren van terrorisme'),
    'NL:uitvoeringsbesluit-wwft': ('BWBR0041193', 'uitvoeringsbesluit-wwft-2018', 'Uitvoeringsbesluit Wwft 2018'),
    'NL:sw1977': ('BWBR0003296', 'sanctiewet-1977', 'Sanctiewet 1977'),
    'NL:rtsw': ('BWBR0018806', 'regeling-toezicht-sanctiewet-1977', 'Regeling toezicht Sanctiewet 1977'),
    'NL:wtt2018': ('BWBR0041259', 'wtt-2018', 'Wet toezicht trustkantoren 2018'),
}
EU = {   # law id: (CELEX, file stem, valid from)
    'EU:amlr': ('32024R1624', 'amlr', '2027-07-10'),
    'NL:tfr': ('32023R1113', 'tfr', '2024-12-30'),
    'EU:2014/269': ('32014R0269', 'sanctions-269-2014', '2014-03-17'),
}


def get(url, path):
    req = urllib.request.Request(url, headers={'User-Agent': 'casefold-law-fetch/1.0'})
    with urllib.request.urlopen(req, timeout=120) as r, open(path, 'wb') as f:
        f.write(r.read())
    h = hashlib.sha256(open(path, 'rb').read()).hexdigest()
    print(f'{os.path.relpath(path, HERE)}  {os.path.getsize(path):,} bytes  sha256 {h[:12]}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--date', default=datetime.date.today().isoformat())
    a = ap.parse_args()
    out = os.path.join(HERE, 'laws', 'sources'); os.makedirs(out, exist_ok=True)
    cmds = []
    for law, (bwb, stem, title) in NL.items():
        p = os.path.join(out, f'{stem}-{a.date}-nl.pdf')
        try:
            get(f'https://wetten.overheid.nl/{bwb}/{a.date}/0/pdf', p)   # the PDF print of the consolidated text valid on that date
            cmds.append(f'python3 casefold/law_ingest.py {os.path.relpath(p, HERE)} --law {law} --version {a.date} --lang nl --title "{title}" --url https://wetten.overheid.nl/{bwb}/{a.date}')
        except Exception as e:
            print(f'{law}: could not download ({e}); download the PDF by hand from https://wetten.overheid.nl/{bwb} and save it as {p}', file=sys.stderr)
    for law, (celex, stem, since) in EU.items():
        for lang in ('nl', 'en'):
            p = os.path.join(out, f'{stem}-{lang}.pdf')
            try:
                get(f'https://eur-lex.europa.eu/legal-content/{lang.upper()}/TXT/PDF/?uri=CELEX:{celex}', p)
                cmds.append(f'python3 casefold/law_ingest.py {os.path.relpath(p, HERE)} --law {law} --version {since} --lang {lang} --url https://eur-lex.europa.eu/eli/reg/{celex[1:5]}/{int(celex[6:])}/oj')
            except Exception as e:
                print(f'{law} ({lang}): could not download ({e}); save the EUR-Lex PDF as {p}', file=sys.stderr)
    print('\nNext:\n  ' + '\n  '.join(cmds) + '\n  python3 casefold/build_duties.py\n  bash run.sh')


if __name__ == '__main__':
    main()
