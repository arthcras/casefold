#!/usr/bin/env python3
"""Dynamic duties: rebuild the legal basis of each duty from the laws that were read in, per legal regime.

    python3 casefold/build_duties.py            # reads data/rules/duty_map.json and laws/*.json, updates data/rules/sector_duties.json

For every duty in duty_map.json and every regime (Wwft until 9 July 2027, AMLR or Iwt from 10 July 2027):
- if the law was read in (laws/<law>@<version>-nl.json, and -en.json for the English text), the basis gets the verbatim
  article, paragraph or point, the source file's sha256, and 'checked' when the expected words occur in it;
- if not, the existing basis stays (Wwft) or the article is listed as 'pending' (AMLR, Iwt), with its number marked to verify.
Each basis has valid_from / valid_to; the next regime's basis says which one it replaces (REPLACED_BY in the graph).
A regime that changes a parameter (EUR 15,000 -> EUR 10,000) adds a successor duty that replaces the old one.
The first run keeps the hand-written basis as basis_manual, so the script can be run again and again.
"""
import glob, json, os, re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = lambda *p: os.path.join(HERE, *p)
J = lambda p, sep: sep.join(p) if isinstance(p, list) else p
NL_ART = lambda law, a, p, q: f"{law} art. {a}" + (f" lid {J(p, ' en ')}" if p else '') + (f" onder {q}" if q else '')
EU_ART = lambda law, a, p, q: f"{law} art. {a}" + (f"({J(p, ') and (')})" if p else '') + (f"({q})" if q else '')


def laws():
    out = {}
    for f in glob.glob(R('laws', '*.json')):
        j = json.load(open(f, encoding='utf-8'))
        k = (j['law'], j['lang'])
        if k not in out or j['version'] > out[k]['version']:
            out[k] = j
    return out


def find(law, ref):
    """The verbatim text of article / paragraph / point in a law that was read in, or None."""
    if not law:
        return None
    art = next((a for a in law['article_list'] if a['number'] == ref.get('article')), None)
    if art is None:
        return None
    text, heading = art['text'], art['heading']
    if ref.get('paragraph'):
        nums = ref['paragraph'] if isinstance(ref['paragraph'], list) else [ref['paragraph']]
        parts = []
        for num in nums:
            p = next((x for x in art['paragraphs'] if x['number'] == num), None)
            if p is None:
                return None
            if ref.get('point'):
                q = next((y for y in p['points'] if y['label'] == ref['point']), None)
                if q is None:
                    return None
                intro = p['text'].strip()
                parts.append((intro + ' ' if intro else '') + f"{q['label']}. {q['text']}")
            else:
                parts.append((f"{num}. " if len(nums) > 1 else '') + p['text'] + ''.join(f" {y['label']}. {y['text']}" for y in p['points']))
        text = ' '.join(parts)
    return {'text': text, 'heading': heading, 'version': law['version'], 'sha256': law['sha256'], 'method': law['method'], 'url': law.get('url', '')} if text else None


def main():
    M = json.load(open(R('data', 'rules', 'duty_map.json'), encoding='utf-8'))
    D = json.load(open(R('data', 'rules', 'sector_duties.json'), encoding='utf-8'))
    L = laws()
    regimes = {r['id']: r for r in M['regimes']}
    known = {l['id'] for l in D['laws']}
    for r in M['regimes']:
        if r['law'] not in known and r.get('title'):
            D['laws'].append({'id': r['law'], 'short': r['short'], 'title': r['title'], 'url': r.get('url', '')}); known.add(r['law'])
    duties = {d['id']: d for d in D['duties']}
    report = []
    for did, refs in M['duties'].items():
        d = duties.get(did)
        if d is None:
            continue
        d.setdefault('basis_manual', d['basis'])
        bases, prev = [], None
        for n, ref in enumerate(refs):
            rg = regimes[ref['regime']]
            law = rg['law']
            fmt = EU_ART if law.startswith('EU:') else NL_ART
            nl, en = find(L.get((law, 'nl')), ref), find(L.get((law, 'en')), ref)
            label = fmt(rg['short'], ref.get('article', '?'), ref.get('paragraph'), ref.get('point')) if ref.get('article') else f"{rg['short']} (article not yet known)"
            b = {'law': law, 'ref': label, 'valid_from': rg.get('valid_from'), 'valid_to': rg.get('valid_to'), 'regime': rg['id']}
            if nl or en:
                words = ref.get('expect', [])
                hay = ' '.join(x['heading'] + ' ' + x['text'] for x in (nl, en) if x).lower()
                ok = not words or any(w.lower() in hay for w in words)
                old = d['basis_manual'][0] if ref['regime'] == 'wwft' else {}
                keep_en = not en and old.get('text_en') and old.get('kind') == 'law'     # no English text read in: keep the translation made earlier
                b.update(kind='law', text=(nl or {}).get('text', ''), text_en=(en or {}).get('text', '') or ref.get('en', '') or (old.get('text_en', '') if keep_en else ''), url=(nl or en)['url'],
                         en_type='official' if en and law.startswith('EU:') else 'unofficial translation (Casefold)' if (en or keep_en or ref.get('en')) else 'none',
                         verify=not ok, read=f"{(nl or en)['method']} of the text valid from {(nl or en)['version']}, sha256 {(nl or en)['sha256'][:12]}",
                         heading=(nl or en)['heading'])
                report.append(f"{did}: {label} read in{'' if ok else ' but the expected words are missing: check the article number'}")
            elif ref['regime'] == 'wwft':
                old = d['basis_manual'][0]
                b.update({k: old.get(k) for k in ('kind', 'text', 'text_en', 'en_type', 'verify', 'url', 'read')})
                b['ref'] = old['ref']
                report.append(f"{did}: {old['ref']} not read in yet: hand-written basis kept")
            else:
                b.update(kind='pending', text='', text_en='', en_type='none', verify=True, url=rg.get('url', ''),
                         read=ref.get('note') or f"text not read in yet; article {ref.get('article')} to verify")
                report.append(f"{did}: {label} pending (law not read in)")
            if prev is not None:
                b['replaces'] = prev
            prev = n
            bases.append(b)
            if ref.get('successor'):
                s = ref['successor']
                new = {**{k: v for k, v in d.items() if k not in ('basis', 'basis_manual')}, **s, 'valid_from': rg['valid_from'], 'valid_to': None,
                       'replaces': did, 'basis': [dict(b, replaces=None)]}
                d['valid_to'] = bases[-2]['valid_to'] if len(bases) > 1 else d.get('valid_to')
                bases.pop()
                D['duties'] = [x for x in D['duties'] if x['id'] != s['id']] + [new]
                report.append(f"{did}: replaced by {s['id']} from {rg['valid_from']}")
        d['basis'] = bases
    for d in D['duties']:     # Dutch search words: Relate's full-text index proposes a section of an uploaded procedure that covers the duty without citing it
        d['search'] = M.get('search', {}).get(d['id'], M.get('search', {}).get(d.get('replaces') or '', ''))
    # every basis gets its law and article number as fields, so a citation in an uploaded text ("artikel 16 Wwft") can find it
    short = {l['id']: l['short'] for l in D['laws']}
    short.update({'NL:wwft': 'Wwft', 'NL:rtsw': 'Rtsw', 'NL:sw1977': 'Sanctiewet', 'NL:wtt2018': 'Wtt', 'EU:amlr': 'AMLR', 'NL:tfr': 'TFR'})
    for d in D['duties']:
        for b in d['basis']:
            m = re.search(r'art\.\s*(\d+[a-z]{0,3})(?:\s*lid\s*(\d+)|\((\d+)\))?', b.get('ref') or '')
            b['law_short'] = short.get(b['law'], b['law'])
            b['art'] = m.group(1) if m else None
            b['lid'] = (m.group(2) or m.group(3)) if m else None
    json.dump(D, open(R('data', 'rules', 'sector_duties.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n'.join(report))
    print(f"laws read in: {', '.join(sorted(f'{k[0]} ({k[1]}) {v["version"]}' for k, v in L.items())) or 'none yet (run casefold/law_fetch.py, then casefold/law_ingest.py)'}")


if __name__ == '__main__':
    main()
