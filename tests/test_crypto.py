"""Casefold Crypto Intelligence: check the crypto data and, when Relate is installed, the register built from it.

  python3 tests/test_crypto.py          data checks, then register/crypto.rl and the queries in queries/crypto/
"""
import json, os, shutil, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, 'casefold'))
import build_crypto  # noqa: E402

failed = 0


def ok(cond, what):
    global failed
    print(('  ok   ' if cond else '  FAIL ') + what)
    failed += 0 if cond else 1


j, c, l = build_crypto.data()
errors = build_crypto.check(j, c, l)
ok(not errors, 'data: every case has an https source, a date, a known jurisdiction, authority and law' + ('' if not errors else ': ' + '; '.join(errors)))
ok(j[0]['code'] == 'NL' and j[0]['wave'] == 1, 'wave 1 is the Netherlands')
arts_in = build_crypto.articles()
ok(all(a['status'] != 'text not read in' for a in arts_in), f'{len(arts_in)} key articles, each found in a law file under laws/ (MiCA, TFR, Wwft)')
nl = {r['id'] for r in j[0]['regulators']}
ok({'NL:afm', 'NL:dnb', 'NL:fiu-nl'} <= nl, 'NL supervisors use the ids of the Casefold register (NL:afm, NL:dnb, NL:fiu-nl)')
known = {x['id'] for x in json.load(open(os.path.join(HERE, 'data', 'rules', 'laws.json'), encoding='utf-8'))['laws']}
ok({'NL:mica', 'NL:tfr', 'NL:wwft', 'NL:sw1977'} <= known & {w['id'] for w in j[0]['laws']}, 'NL laws are the laws Casefold already holds (MiCA, TFR, Wwft, Sanctiewet)')
src = {x['id']: x for x in json.load(open(os.path.join(HERE, 'data', 'sources', 'index.json'), encoding='utf-8'))['cases']}
for k in c['cases']:
    if k['id'] in src:
        ok(k['url'] == src[k['id']]['url'] and src[k['id']]['date'] in (k['date'], k.get('published')), f"{k['id']}: same source as data/sources/index.json, and its date (imposed or published)")
ok(all(k['verify'] or k['amount'] is not None or not k['measure'].endswith('fine') for k in c['cases']), 'a fine without an amount is marked verify')
nl_cases = [k for k in c['cases'] if k['jurisdiction'] == 'NL']
ok(len(nl_cases) >= 9 and all(k['url'].startswith(('https://www.dnb.nl', 'https://www.afm.nl', 'https://www.om.nl')) for k in nl_cases), f'{len(nl_cases)} Dutch cases, each from the DNB, AFM or OM site itself')
wwft_n = sum(1 for k in c['cases'] if any(v['law'] == 'NL:wwft' for v in k['violated']))

rel = os.environ.get('RELATE_BIN') or shutil.which('relate') or os.path.expanduser('~/.local/bin/relate')
if not os.path.exists(rel or ''):
    print('  (skipping the Relate part: relate not installed)')
else:
    from build_case import run
    os.environ['RELATE_BIN'] = rel
    sys.argv = ['build_crypto.py']
    build_crypto.main()
    db = os.path.join(HERE, 'register', 'crypto.rl')
    q = build_crypto.queries()
    reg = run(rel, db, {}, command=q['01_register'], read=True)
    ok(len(reg) == len(j) and reg[0]['code'] == 'NL', f'01 register: {len(reg)} jurisdictions, the Netherlands first')
    nlrow = reg[0]
    ok(any(s.startswith('AFM') for s in nlrow['supervisors']) and any(s.startswith('DNB') for s in nlrow['supervisors']), '01 register: AFM and DNB supervise crypto in NL')
    cases = run(rel, db, {}, command=q['02_cases'], read=True)
    ok(len(cases) == len(c['cases']) and cases[0]['country'] == 'NL', f'02 cases: {len(cases)} cases, Dutch cases first')
    ok(all(r['source'] for r in cases), '02 cases: every case has its source')
    by = {r['law']: r for r in run(rel, db, {}, command=q['03_cases_by_law'], read=True)}
    ok(by.get('18 USC 1960', {}).get('cases') == 4, '03 by law: four cases on unlicensed money transmitting (18 USC 1960)')
    ok(by.get('Wwft', {}).get('cases') == wwft_n, f'03 by law: {wwft_n} Dutch registration cases on the Wwft')
    lists = run(rel, db, {}, command=q['04_sanctions_lists'], read=True)
    ok(len(lists) == len(l), f'04 sanctions lists: {len(lists)}')
    ofac = next((x for x in lists if x['list'].startswith('OFAC')), {})
    ok(ofac.get('imported') and (ofac.get('entries') or 0) > 10000 and (ofac.get('addresses') or 0) > 500, f"04 OFAC SDN imported: {ofac.get('entries')} entries, {ofac.get('addresses')} crypto addresses")
    g = run(rel, db, {}, read=True, command="MATCH (:Entity {id: 'ENTITY:garantex'})-[:POSSIBLY_SAME]->(e:Entity)<-[:LISTS]-(l:SanctionsList) RETURN collect(DISTINCT l.id) AS lists")
    ok(g and 'LIST:ofac-sdn' in g[0]['lists'], 'Garantex in the cases is linked, as a lead, to its listing on the OFAC SDN list')
    hits = run(rel, db, {'q': 'sanctions'}, command=q['05_search_cases'], read=True)
    ok(any('Bittrex' in h['party'] for h in hits), '05 full text: "sanctions" finds Bittrex')

    same = {r['group']: r for r in run(rel, db, {}, command=q['06_same_party_elsewhere'], read=True)}
    ok({'binance', 'okx', 'kucoin'} <= set(same) and all(same[g]['countries'] == 2 for g in ('binance', 'okx', 'kucoin')), '06 same party: Binance, OKX and KuCoin went wrong in the Netherlands and in the US')

    arts = {r['article']: r for r in run(rel, db, {}, command=q['07_articles'], read=True)}
    ok(arts.get('Wwft art. 23b', {}).get('cases') == 6 and arts.get('Wwft art. 23c', {}).get('cases') == 6, '07 articles: six Dutch decisions on Wwft art. 23b and 23c, read from the decisions')
    ok(arts['Wwft art. 23b']['replaced_by'] == 'MiCAR art. 59' and arts['Wwft art. 23b']['status'] == 'vervallen', '07 articles: Wwft art. 23b has lapsed and is replaced by MiCAR art. 59')
    ok(arts.get('MiCAR art. 59', {}).get('status') == 'in force' and arts.get('TFR art. 14', {}).get('status') == 'in force', '07 articles: MiCAR art. 59 and TFR art. 14 read in from EUR-Lex')

    exp = run(rel, db, {'entity': 'OFAC:55045'}, command=q['08_exposure'], read=True)
    ok(len(exp) > 50 and any(r['counterparty'] == 'tron:TTVJjdzirNgbv3aG95Jc9JiH4nvWnxXD32' and r['received_from'] > 1e6 for r in exp), f'08 exposure: Grinex has {len(exp)} counterparties on chain; TTVJjdzi... sent it more than 1 million USDT')
    flows = run(rel, db, {}, read=True, command="MATCH ()-[f:SENT]->() RETURN count(f) AS n, collect(DISTINCT f.asset) AS assets")
    ok(flows[0]['n'] > 500 and not any(a.endswith('*') for a in flows[0]['assets']), f"on-chain flows: {flows[0]['n']}, assets {sorted(flows[0]['assets'])}, no lookalike tokens")
    ty = {r['id']: r for r in run(rel, db, {}, command=q['10_typologies'], read=True)}
    ok(ty['sanctions']['entities'] >= 100 and ty['terrorist_financing']['entities'] > 0 and ty['unlicensed_service']['cases'] >= 9, f"10 typologies: {ty['sanctions']['entities']} listed entities, {ty['terrorist_financing']['entities']} for terrorist financing, {ty['unlicensed_service']['cases']} cases of unlicensed service")

print(f'crypto: {"all pass" if not failed else str(failed) + " failed"}')
sys.exit(1 if failed else 0)
