#!/usr/bin/env python3
"""Test offices and test clients for the Netherlands.

For every sector under Wwft supervision (data/sectors.json) there is one fictitious test office, supervised by that sector's
supervisor. Each office has two test clients. The UBO question is always asked from the office, under the Dutch rule
(Uitvoeringsbesluit Wwft 2018, art. 3), ground by ground for the client's legal form. Together the scenarios cover every Dutch
legal form and every ground: shares and votes (more than 25%), economic ownership through depositary receipts, control through a
majority-held holding, control via other means (a veto), votes on amending the statutes (foundation, association, cooperative),
votes on amending the partnership agreement, the listed-company exception (issuer and 100% subsidiary), the fallback to senior
management (directors; for a partnership every partner except a lender), trust roles, the group of participants of a fund for
joint account (150 or more), a branch (test the foreign parent) and a natural person (no UBO test).

The expected answer (tests/expected.json) is computed here by an independent implementation of art. 3, not by the Cypher query.
usage:  python3 casefold/make_test_cases.py
"""
from datetime import date
import hashlib, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_case import HERE

SECTORS = json.load(open(os.path.join(HERE, 'data', 'sectors.json'), encoding='utf-8'))['sectors']
RULE = json.load(open(os.path.join(HERE, 'data', 'rules', 'ubo_rules.json'), encoding='utf-8'))['rules'][0]
OUT = os.path.join(HERE, 'data', 'testcases')
P = lambda i, n, **k: {'id': i, 'kind': 'Person', 'name': n, 'country': 'NL', **k}
C = lambda i, n, lf=None, **k: {'id': i, 'kind': 'Company', 'name': n, 'country': 'NL', **({'legal_form': lf} if lf else {}), **k}
own = lambda a, b, pct, votes=None, **k: {'from': a, 'to': b, 'type': 'OWNS', 'pct': pct, **({'votes': votes} if votes is not None else {}), 'source': 'D1', 'where': 'register', **k}
director = lambda a: {'from': a, 'to': 'client', 'type': 'DIRECTOR_OF', 'source': 'D1', 'where': 'register'}


def S_BV_STAK(t):
    return 'NL:lf:bv', 'B.V. with a trust foundation (STAK), a majority-held holding and a veto', [
        P('A', f'{t} A (25% direct)'), P('Cm', f'{t} C (96% of the holding)'), P('D', f'{t} D (2% and a veto)'), P('E', f'{t} E (board of the STAK)'),
        P('F', f'{t} F (depositary receipts)'), P('M', f'{t} M (director)'),
        {'id': 'STAK', 'kind': 'Foundation', 'name': f'Stichting Administratiekantoor {t}', 'country': 'NL', 'legal_form': 'NL:lf:stichting'},
        C('H', f'{t} Holding B.V.', 'NL:lf:bv'), C('W', f'{t} Widely Held Fund')], [
        own('A', 'client', 25), own('STAK', 'client', 26), own('F', 'STAK', 100, 0, kind='certificates'),
        {'from': 'E', 'to': 'STAK', 'type': 'BOARD_OF', 'votes': 100, 'source': 'D2', 'where': 'statutes'},
        own('H', 'client', 26), own('Cm', 'H', 96), own('D', 'client', 2),
        {'from': 'D', 'to': 'client', 'type': 'CONTROLS', 'basis': 'veto on budget and directors', 'means': 'veto rights', 'source': 'D3', 'where': 'art. 4'},
        own('W', 'client', 21), director('M')], {}


def S_BV_SIMPLE(t):
    return 'NL:lf:bv', 'B.V. with two shareholders, 60% and 40%', [P('A', f'{t} A (60%)'), P('B', f'{t} B (40%)'), P('M', f'{t} M (director)')], [
        own('A', 'client', 60), own('B', 'client', 40), director('M')], {}


def S_BV_KYCC(t):
    lf, d, e, r, x = S_BV_SIMPLE(t)
    return lf, 'B.V. with two shareholders and high-risk counterparties', e, r, {'counterparties': [
        {'id': 'K1', 'name': f'{t} Gulf Trading FZE', 'type': 'organisation', 'role': 'customer', 'country': 'AE', 'incoming': 2600000, 'outgoing': 0, 'transactions': 9, 'kycc_level': 'full', 'checks_done': 1, 'checks_total': 4, 'offshore': True},
        {'id': 'K2', 'name': f'{t} Coastline Fuel', 'type': 'organisation', 'role': 'supplier', 'country': 'IR', 'incoming': 0, 'outgoing': 85000, 'transactions': 2, 'kycc_level': 'full', 'checks_done': 0, 'checks_total': 4, 'high_risk': True,
         'screening_hit': {'list': 'EU consolidated list (test)', 'matched': 'Coastline Fuel Co. (test)', 'score': 91}},
        {'id': 'K3', 'name': f'{t} Dijk Verpakkingen B.V.', 'type': 'organisation', 'role': 'supplier', 'country': 'NL', 'incoming': 0, 'outgoing': 240000, 'transactions': 12, 'kycc_level': 'light', 'checks_done': 2, 'checks_total': 2}]}


def S_BV_NONE(t):
    return 'NL:lf:bv', 'B.V. with five shareholders of 20% each: nobody qualifies, fallback to the directors', \
        [P(f'S{i}', f'{t} S{i} (20%)') for i in range(1, 6)] + [P('M1', f'{t} M1 (director)'), P('M2', f'{t} M2 (director)')], \
        [own(f'S{i}', 'client', 20) for i in range(1, 6)] + [director('M1'), director('M2')], {}


def S_NV_LISTED(t):
    return 'NL:lf:nv', 'N.V. that is itself a listed issuer: excepted, fallback to the directors', [P('G', f'{t} G (30% of the shares)'), P('M1', f'{t} M1 (director)'), P('M2', f'{t} M2 (director)')], [
        own('G', 'client', 30), director('M1'), director('M2')], {'listed': True}


def S_BV_SUB_OF_LISTED(t):
    return 'NL:lf:bv', 'B.V. held 100% by a listed issuer: excepted, fallback to the directors', [
        C('L', f'{t} Holdings N.V. (listed)', 'NL:lf:nv', listed=True, exchange='regulated market'), P('G', f'{t} G (60% of the listed parent)'), P('M', f'{t} M (director)')], [
        own('L', 'client', 100), own('G', 'L', 60), director('M')], {}


def S_STICHTING_3(t):
    return 'NL:lf:stichting', 'Stichting with three board members who decide on the statutes (33.3% of the votes each)', [P(f'B{i}', f'{t} B{i} (board)') for i in range(1, 4)], [
        {'from': f'B{i}', 'to': 'client', 'type': 'BOARD_OF', 'votes': 33.3, 'source': 'D1', 'where': 'statutes art. 9'} for i in range(1, 4)] + [director(f'B{i}') for i in range(1, 4)], {}


def S_STICHTING_5(t):
    return 'NL:lf:stichting', 'Stichting with five board members (20% each): nobody qualifies, fallback to the board', [P(f'B{i}', f'{t} B{i} (board)') for i in range(1, 6)], [
        {'from': f'B{i}', 'to': 'client', 'type': 'BOARD_OF', 'votes': 20, 'source': 'D1', 'where': 'statutes art. 9'} for i in range(1, 6)] + [director(f'B{i}') for i in range(1, 6)], {}


def S_VERENIGING(t):
    return 'NL:lf:vereniging', 'Vereniging: members each under 25% of the votes, one founder with actual control', [
        P('F', f'{t} F (founder, appoints the board)'), P('V1', f'{t} V1 (member, 10%)'), P('V2', f'{t} V2 (member, 10%)'), P('M', f'{t} M (chair)')], [
        {'from': 'V1', 'to': 'client', 'type': 'MEMBER_OF', 'votes': 10, 'source': 'D1', 'where': 'members register'},
        {'from': 'V2', 'to': 'client', 'type': 'MEMBER_OF', 'votes': 10, 'source': 'D1', 'where': 'members register'},
        {'from': 'F', 'to': 'client', 'type': 'CONTROLS', 'basis': 'appoints and dismisses the board under the statutes', 'means': 'appointment rights', 'source': 'D1', 'where': 'statutes art. 7'},
        director('M')], {}


def S_COOP(t):
    return 'NL:lf:cooperatie', 'Coöperatie U.A. with two members of 50% each', [P('A', f'{t} A (member, 50%)'), P('B', f'{t} B (member, 50%)'), P('M', f'{t} M (director)')], [
        own('A', 'client', 50), own('B', 'client', 50), director('M')], {}


def S_VOF(t):
    return 'NL:lf:vof', 'V.O.F. with two partners, 70% and 30%', [P('A', f'{t} A (partner, 70%)'), P('B', f'{t} B (partner, 30%)')], [
        own('A', 'client', 70), own('B', 'client', 30)], {}


def S_CV(t):
    return 'NL:lf:cv', 'C.V.: a managing partner with the votes and three limited partners', [
        P('G', f'{t} G (managing partner, 2%)'), P('L1', f'{t} L1 (limited partner, 40%)'), P('L2', f'{t} L2 (limited partner, 30%)'), P('L3', f'{t} L3 (limited partner, 28%)')], [
        own('G', 'client', 2, 100), own('L1', 'client', 40, 0), own('L2', 'client', 30, 0), own('L3', 'client', 28, 0)], {}


def S_MAATSCHAP(t):
    return 'NL:lf:maatschap', 'Maatschap with four partners of 24% and a lender: nobody qualifies, fallback to every partner except the lender', [
        P(f'V{i}', f'{t} V{i} (partner, 24%)') for i in range(1, 5)] + [P('Q', f'{t} Q (partner by way of a loan, 4%)')], [
        own(f'V{i}', 'client', 24) for i in range(1, 5)] + [own('Q', 'client', 4, 0, lender=True)], {}


def S_FGR(t):
    return 'NL:lf:fgr', 'Fund for joint account offered to 412 participants, with a licensed manager', [
        {'id': 'GRP', 'kind': 'Group', 'name': f'{t} participants of the fund (group of 412)', 'country': 'NL'}, C('BH', f'{t} Fund Management B.V.', 'NL:lf:bv')], [
        {'from': 'GRP', 'to': 'client', 'type': 'ROLE_IN', 'role': 'fgr_group', 'source': 'D1', 'where': 'prospectus'},
        {'from': 'BH', 'to': 'client', 'type': 'ROLE_IN', 'role': 'manager', 'source': 'D1', 'where': 'licence art. 2:65 Wft'}], {'participants': 412, 'licensed_manager': True}


def S_TRUST(t):
    return 'NL:lf:foreign-trust', 'Foreign express trust administered in the Netherlands', [
        P('S', f'{t} S (settlor)'), P('T', f'{t} T (trustee)'), P('R', f'{t} R (protector)'), P('B1', f'{t} B1 (beneficiary)'), P('B2', f'{t} B2 (beneficiary)')], [
        {'from': x, 'to': 'client', 'type': 'ROLE_IN', 'role': r, 'source': 'D1', 'where': 'trust deed'} for x, r in
        (('S', 'founder'), ('T', 'trustee'), ('R', 'protector'), ('B1', 'beneficiary'), ('B2', 'beneficiary'))], {}


def S_BRANCH(t):
    return 'NL:lf:branch', 'Dutch branch of a foreign company: test the foreign parent', [
        C('PAR', f'{t} Parent Ltd (foreign)'), P('A', f'{t} A (80% of the parent)'), P('B', f'{t} B (20% of the parent)'), P('M', f'{t} M (branch manager)')], [
        own('PAR', 'client', 100), own('A', 'PAR', 80), own('B', 'PAR', 20), director('M')], {}


def S_PERSON(t):
    return None, 'Natural person: no UBO test (the client is the natural person)', [], [], {'person': True}


PLAN = {'banks': (S_BV_STAK, S_NV_LISTED), 'non-bank-lending': (S_BV_SIMPLE, S_VOF), 'payment-institutions': (S_BV_KYCC, S_BV_SUB_OF_LISTED),
        'electronic-money': (S_BV_NONE, S_COOP), 'currency-exchange': (S_PERSON, S_BV_SIMPLE), 'payment-service-agents': (S_VOF, S_PERSON),
        'life-insurers': (S_COOP, S_NV_LISTED), 'banks-and-e-money': (S_BV_STAK, S_BRANCH), 'trust-offices': (S_TRUST, S_BV_STAK),
        'investment-firms': (S_FGR, S_BV_SUB_OF_LISTED), 'investment-institutions': (S_FGR, S_CV), 'ucits': (S_FGR, S_NV_LISTED),
        'financial-service-providers': (S_PERSON, S_BV_SIMPLE), 'crypto-asset': (S_BV_STAK, S_BRANCH), 'external-accountants': (S_MAATSCHAP, S_STICHTING_5),
        'tax-advisers': (S_BV_NONE, S_VERENIGING), 'civil-law-notaries': (S_STICHTING_3, S_CV), 'other-independent-legal': (S_VOF, S_STICHTING_5),
        'lawyers': (S_MAATSCHAP, S_TRUST), 'domicile': (S_BV_STAK, S_BRANCH), 'real-estate-brokers': (S_CV, S_PERSON), 'real-estate-appraisers': (S_BV_SIMPLE, S_VERENIGING),
        'professional-traders': (S_PERSON, S_BV_KYCC), 'intermediaries-in-vehicles': (S_BV_NONE, S_PERSON), 'art-dealers': (S_PERSON, S_STICHTING_3),
        'pawnshops': (S_PERSON, S_VOF), 'land-based-casinos': (S_PERSON, S_BV_SIMPLE), 'online-gambling': (S_PERSON, S_BV_KYCC),
        # sectors that come under supervision with the AMLR (2027; football 2029)
        'crowdfunding': (S_BV_SIMPLE, S_BV_KYCC), 'mortgage-and-consumer-credit': (S_PERSON, S_BV_SIMPLE), 'dealers-in-precious': (S_BV_NONE, S_PERSON),
        'dealers-in-high-value': (S_BV_SIMPLE, S_PERSON), 'free-zones': (S_BV_KYCC, S_BV_SUB_OF_LISTED), 'investment-migration': (S_PERSON, S_TRUST),
        'non-financial-mixed-holding': (S_BV_STAK, S_NV_LISTED),
        # supervised, but not obliged entities under the Wwft or the AMLR
        'pension-funds': (S_STICHTING_5, S_PERSON), 'non-life-insurers': (S_BV_SIMPLE, S_PERSON), 'non-life-insurance-intermediaries': (S_PERSON, S_VOF),
        'audit-firms': (S_BV_KYCC, S_NV_LISTED), 'listed-issuers': (S_NV_LISTED, S_BV_STAK), 'lotteries': (S_PERSON, S_STICHTING_3),
        'gaming-arcades': (S_PERSON, S_BV_SIMPLE), 'bailiffs': (S_PERSON, S_BV_NONE), 'football-agents': (S_PERSON, S_BV_SIMPLE), 'professional-football-clubs': (S_BV_NONE, S_VERENIGING)}
ENTITY = {'NL:lf:bv': 'corporate', 'NL:lf:nv': 'corporate', 'NL:lf:branch': 'corporate', 'NL:lf:stichting': 'other_legal_entity', 'NL:lf:vereniging': 'other_legal_entity',
          'NL:lf:cooperatie': 'other_legal_entity', 'NL:lf:vof': 'partnership', 'NL:lf:cv': 'partnership', 'NL:lf:maatschap': 'partnership',
          'NL:lf:fgr': 'trust', 'NL:lf:foreign-trust': 'trust'}
EXTRA_LF = [{'id': 'NL:lf:foreign-trust', 'country': 'NL', 'local': 'buitenlandse trust (beheerd in Nederland)', 'abbr': 'trust', 'en': 'foreign express trust', 'category': 'trust',
             'law': 'Hague Trust Convention; Uitvoeringsbesluit Wwft 2018 art. 3(1)(e)', 'law_url': '', 'registered_in': 'UBO-register (trusts)', 'ubo_rule': 'Art. 3(1)(e): founder, trustee, protector, beneficiaries, other controllers',
             'verify': False, 'legal_personality': False, 'entity_type': 'trust'}]


def expected(lf, entities, rels, extra):
    """Independent implementation of art. 3 Uitvoeringsbesluit Wwft 2018 for the test structures."""
    if lf is None:
        return {}, []
    et = ENTITY[lf]
    names = {e['id']: e['name'] for e in entities}
    out = {}
    if et == 'corporate' and (extra.get('listed') or any(r['type'] == 'OWNS' and r['to'] == 'client' and r['pct'] == 100 and next((e for e in entities if e['id'] == r['from']), {}).get('listed') for r in rels)):
        out = {}
    elif et == 'trust':
        for r in rels:
            if r['type'] == 'ROLE_IN' and r['role'] in ('founder', 'trustee', 'protector', 'beneficiary', 'other_controller'):
                out.setdefault(names[r['from']], set()).add(r['role'])
            if r['type'] == 'ROLE_IN' and r['role'] == 'fgr_group' and extra.get('participants', 0) >= 150 and extra.get('licensed_manager'):
                out.setdefault(names[r['from']], set()).add('fgr_group')
    else:
        def paths(node, kinds, acc, seen):
            if node == 'client':
                yield acc; return
            for r in rels:
                if r['from'] == node and r['type'] in kinds and r['to'] not in seen:
                    yield from paths(r['to'], kinds, acc + [r], seen | {r['to']})
        vote_key = {'corporate': 'voting_rights', 'other_legal_entity': 'statute_votes', 'partnership': 'agreement_votes'}[et]
        for e in entities:
            if e['kind'] not in ('Person',):
                continue
            o_m = o_c = v_m = v_c = 0.0
            for p in paths(e['id'], ('OWNS',), [], {e['id']}):
                m = c = 1.0
                for i, r in enumerate(p):        # through control: an intermediate the person controls passes on its whole stake; the last link counts as is
                    m *= r['pct'] / 100; c *= 1.0 if (i < len(p) - 1 and r.get('votes', r['pct']) > 50) else r['pct'] / 100
                o_m += m; o_c += c
            for p in paths(e['id'], ('OWNS', 'BOARD_OF', 'MEMBER_OF'), [], {e['id']}):
                m = c = 1.0
                for i, r in enumerate(p):
                    v = r.get('votes', r.get('pct', 0)); m *= v / 100; c *= 1.0 if (i < len(p) - 1 and v > 50) else v / 100
                v_m += m; v_c += c
            own_, vot = round(100 * max(o_m, o_c), 1), round(100 * max(v_m, v_c), 1)
            met = set()
            if own_ > 25: met.add('ownership_interest')
            if vot > 25: met.add(vote_key)
            if any(r['type'] == 'CONTROLS' and r['from'] == e['id'] for r in rels): met.add('control_other_means')
            if met: out[e['name']] = met
    out = {k: sorted(v) for k, v in out.items()}
    fallback = []
    if not out and et in ('corporate', 'other_legal_entity'):
        fallback = sorted({names[r['from']] for r in rels if r['type'] == 'DIRECTOR_OF'})
    if not out and et == 'partnership':
        fallback = sorted({names[r['from']] for r in rels if r['type'] == 'OWNS' and r['to'] == 'client' and not r.get('lender')})
    return out, fallback


def T(i, kind, amount, payment, what):
    return {'id': i, 'date': '2026-10-15', 'kind': kind, 'amount': amount, 'payment': payment, 'description': what}


# transactions per sector: client 1 triggers the sector's thresholds, client 2 stays below them
TX = {
    'currency-exchange': ([T('T1', 'occasional', 16000, 'cash', 'exchange of cash into USD'), T('T2', 'cash_import', 12000, 'cash', 'USD cash brought in from outside the EU')], [T('T1', 'occasional', 900, 'cash', 'exchange of cash into USD')]),
    'banks-and-e-money': ([T('T1', 'crypto_transfer', 1500, 'transfer', 'crypto transfer to a self-hosted address')], []),
    'crypto-asset-service': ([T('T1', 'crypto_transfer', 1200, 'transfer', 'crypto transfer to another provider')], []),
    'banks': ([T('T1', 'transfer', 5000, 'transfer', 'outgoing SEPA transfer')], []),
    'payment-institutions': ([T('T1', 'transfer', 2500, 'transfer', 'money transfer abroad')], []),
    'electronic-money': ([T('T1', 'transfer', 120, 'transfer', 'payment from an e-money account')], []),
    'payment-service-agents': ([T('T1', 'transfer', 800, 'transfer', 'money transfer abroad')], []),
    'investment': ([T('T1', 'occasional', 20000, 'transfer', 'one-off purchase of fund units')], [T('T1', 'occasional', 5000, 'transfer', 'one-off purchase of fund units')]),
    'ucits': ([T('T1', 'occasional', 20000, 'transfer', 'one-off purchase of fund units')], [T('T1', 'occasional', 5000, 'transfer', 'one-off purchase of fund units')]),
    'life-insurers': ([T('T1', 'occasional', 15000, 'transfer', 'single premium')], []),
    'non-bank-lending': ([T('T1', 'occasional', 15000, 'transfer', 'one-off loan disbursement')], []),
    'financial-service-providers': ([T('T1', 'occasional', 15000, 'transfer', 'single premium via the intermediary')], []),
    'land-based-casinos': ([T('T1', 'prize', 2400, 'cash', 'prize collected at the cashier'), T('T2', 'deposit', 12000, 'cash', 'chips bought with cash')], [T('T1', 'bet', 1500, 'cash', 'bet at the table')]),
    'online-gambling': ([T('T1', 'deposit', 16000, 'transfer', 'deposit to the player account')], [T('T1', 'deposit', 900, 'transfer', 'deposit to the player account')]),
    'professional-traders': ([T('T1', 'sale', 4200, 'cash', 'used car paid in cash'), T('T2', 'sale', 25000, 'transfer', 'car paid by bank transfer')], [T('T1', 'sale', 2800, 'cash', 'scooter paid in cash')]),
    'art-dealers': ([T('T1', 'sale', 12000, 'transfer', 'painting paid by bank transfer'), T('T2', 'sale', 3500, 'cash', 'print paid in cash')], [T('T1', 'sale', 6000, 'transfer', 'drawing paid by bank transfer')]),
    'pawnshops': ([T('T1', 'pledge', 800, 'cash', 'loan against a watch'), T('T2', 'sale', 3100, 'cash', 'sale of an unredeemed ring')], [T('T1', 'pledge', 300, 'cash', 'loan against a phone')]),
    'real-estate-brokers': ([T('T1', 'rent_month', 12500, 'transfer', 'monthly rent of a villa'), T('T2', 'deposit', 11000, 'cash', 'deposit paid in cash')], [T('T1', 'rent_month', 2400, 'transfer', 'monthly rent of an apartment')]),
    'real-estate-appraisers': ([T('T1', 'fee', 10500, 'cash', 'valuation fee paid in cash')], [T('T1', 'fee', 900, 'transfer', 'valuation fee')]),
    'dealers-in-precious': ([T('T1', 'sale', 3600, 'cash', 'gold bars paid in cash')], [T('T1', 'sale', 2500, 'cash', 'gold coins paid in cash')]),
    'dealers-in-high-value': ([T('T1', 'sale', 12000, 'transfer', 'watch paid by bank transfer'), T('T2', 'sale', 5000, 'cash', 'bag paid in cash')], [T('T1', 'sale', 900, 'cash', 'belt paid in cash')]),
    'crowdfunding': ([T('T1', 'occasional', 12000, 'transfer', 'investment in a crowdfunding project')], [T('T1', 'occasional', 500, 'transfer', 'investment in a crowdfunding project')]),
    'intermediaries-in-vehicles': ([T('T1', 'brokered_sale', 80000, 'transfer', 'brokered sale of a yacht')], [T('T1', 'brokered_sale', 4000, 'transfer', 'brokered sale of a motorbike')]),
}
SERVICE = {'tax-advisers': 'tax advice on setting up a holding company', 'civil-law-notaries': 'deed of transfer of registered property',
           'other-independent-legal': 'assistance with setting up a company', 'lawyers': 'assistance with buying registered property'}
ON = os.environ.get('CASEFOLD_ON') or date.today().isoformat()   # the date the expected answers are computed for
UBO_RULE_UNTIL = json.load(open(os.path.join(HERE, 'data', 'rules', 'ubo_rules.json'), encoding='utf-8'))['rules'][0]['valid_to'] or '9999-12-31'
BTYPES = json.load(open(os.path.join(HERE, 'data', 'business_types.json'), encoding='utf-8'))
SCEN_BT = {'S_BV_STAK': 'holding_spv', 'S_NV_LISTED': 'listed_group', 'S_BV_SUB_OF_LISTED': 'listed_group', 'S_PERSON': 'private_individual', 'S_BV_KYCC': 'trading',
           'S_BV_SIMPLE': 'cash_intensive', 'S_BV_NONE': 'construction', 'S_STICHTING_3': 'charity', 'S_STICHTING_5': 'charity', 'S_VERENIGING': 'charity',
           'S_COOP': 'real_estate', 'S_VOF': 'cash_intensive', 'S_CV': 'real_estate', 'S_MAATSCHAP': 'consultancy', 'S_FGR': 'real_estate', 'S_TRUST': 'personal_holding',
           'S_BRANCH': 'trading'}


def business_type(scen, slug):
    code = 'sports_club' if slug.startswith('professional-football') and scen.__name__ != 'S_PERSON' else SCEN_BT.get(scen.__name__, 'consultancy')
    t = BTYPES['types'][code]
    factors = [{'id': f, **BTYPES['factors'][f]} for f in t['factors']]
    band = 'high' if any(f['annex'] == 'III' for f in factors) else 'low' if factors else 'medium'
    return {'code': code, 'sbi': t['sbi'], 'name': t['name'], 'name_nl': t['name_nl'], 'factors': factors}, band


DUTIES = json.load(open(os.path.join(HERE, 'data', 'rules', 'sector_duties.json'), encoding='utf-8'))


# ---- the service the client uses (onboarding), its sub-clients (KYCC) and a series of transactions (monitoring) ----
SERVICE_BY_GROUP = {   # sector group -> (service, expected amount per month in EUR, cash expected)
    'bank': ('business payment account', 50000, False), 'payment': ('payment and money transfer service', 10000, False),
    'insurance': ('life insurance with a single premium', 2000, False), 'crypto': ('crypto-asset custody and trading account', 5000, False),
    'trust': ('management and registered office of a holding company', 20000, False), 'investment': ('investment account / participation in a fund', 10000, False),
    'accountant': ('annual accounts and tax returns', 3000, False), 'notary': ('transfer of registered property via the third-party account', 400000, False),
    'lawyer': ('assistance with buying registered property (third-party funds)', 300000, False), 'real_estate': ('brokerage of a sale or a rental', 15000, False),
    'dealer': ('sale of goods', 8000, True), 'other': ('services', 5000, False), 'gaming': ('player account', 2000, True),
    'credit': ('mortgage intermediation', 5000, False), 'football': ('player transfer and sponsorship', 200000, False)}
SERVICE_BY_KEY = {'pension-funds': ('pension scheme administration', 50000, False), 'non-life-insurers': ('non-life insurance policy', 500, False), 'audit-firms': ('statutory audit', 5000, False), 'listed-issuers': ('shareholder services', 10000, False), 'lotteries': ('lottery ticket subscription', 50, False), 'gaming-arcades': ('arcade visit', 300, True), 'bailiffs': ('debt collection', 3000, False), 'crowdfunding': ('investor account on a crowdfunding platform', 5000, False), 'pawnshops': ('pawn loan', 2000, True), 'domicile': ('registered address', 500, False), 'online-gambling': ('online player account', 2000, False),
                  'non-financial-mixed-holding': ('group treasury', 100000, False), 'investment-migration': ('residence-by-investment application', 50000, False)}
MON = json.load(open(os.path.join(HERE, 'data', 'rules', 'monitoring_rules.json'), encoding='utf-8'))['rules']
HIGH_RISK = next(r for r in MON if r['check'] == 'high_risk_country')['countries']


def day(d):
    return (date.fromisoformat(d) - date(1970, 1, 1)).days


def service_for(sec):
    k = next((k for k in sorted(SERVICE_BY_KEY, key=len, reverse=True) if sec['slug'].startswith(k)), None)
    name, monthly, cash = SERVICE_BY_KEY[k] if k else SERVICE_BY_GROUP.get(sec['group'], SERVICE_BY_GROUP['other'])
    return {'name': name, 'expected_monthly': monthly, 'cash_allowed': cash}


def monitoring(tag, n, svc, limit):
    """Three sub-clients (KYCC), each with a role, and one sub-client of a sub-client (second level), plus a series of transactions.
    Client 1 deviates from its profile; client 2 stays within it. S1 is the same company for both clients of an office, so the
    office file can see a counterparty that recurs across its clients (by a one-way key, without the name)."""
    e = svc['expected_monthly']
    office_tag = tag[:-1]
    if n == 1:
        subs = [('S1', f'{office_tag} Noordlicht Handel B.V.', 'NL', 4, 4, None, 'customer', None),
                ('S2', f'{tag} Pars Trading Co.', 'IR', 1, 4, None, 'supplier', None),
                ('S3', f'{tag} Harbour Logistics FZE', 'AE', 2, 4, {'list': 'EU consolidated list (test)', 'matched': 'Harbour Logistic FZE (test)', 'score': 88}, 'intermediary (agent)', None),
                ('S1A', f'{tag} Volga Metals LLC', 'RU', 0, 2, None, 'supplier of S1', 'S1')]
        tx = [('M1', '2026-07-05', round(e * 0.8), 'transfer', 'S1'), ('M2', '2026-08-03', e * 8, 'transfer', 'S2'),
              ('M3', '2026-09-10', round(limit * 0.9), 'cash', 'S1'), ('M4', '2026-09-13', round(limit * 0.95), 'cash', 'S1'), ('M5', '2026-10-02', 4000, 'transfer', 'S3')]
    else:
        subs = [('S1', f'{office_tag} Noordlicht Handel B.V.', 'NL', 2, 2, None, 'customer', None),
                ('S2', f'{tag} Rheinland Service GmbH', 'DE', 2, 2, None, 'supplier', None),
                ('S3', f'{tag} Schelde Diensten BV', 'BE', 2, 2, None, 'payment service provider', None),
                ('S1A', f'{tag} Twente Logistiek B.V.', 'NL', 2, 2, None, 'supplier of S1', 'S1')]
        tx = [('M1', '2026-07-06', round(e * 0.6), 'transfer', 'S1'), ('M2', '2026-08-04', round(e * 0.7), 'transfer', 'S2'),
              ('M3', '2026-09-08', round(e * 0.5), 'transfer', 'S3'), ('M4', '2026-10-05', round(e * 0.9), 'transfer', 'S1')]
    cps = []
    for sid, name, cc, done, total, hit, role, parent in subs:
        mine = [t for t in tx if t[4] == sid]
        cps.append({'id': sid, 'name': name, 'type': 'organisation', 'role': role, 'country': cc, 'parent': parent,
                    'key': hashlib.sha256(f'{name}|{cc}'.encode()).hexdigest()[:12],
                    'incoming': sum(t[2] for t in mine), 'outgoing': 0, 'transactions': len(mine), 'kycc_level': 'full' if cc in HIGH_RISK or hit else 'light',
                    'checks_done': done, 'checks_total': total, **({'high_risk': True} if cc in HIGH_RISK else {}), **({'screening_hit': hit} if hit else {})})
    txs = [{'id': i, 'date': d, 'day': day(d), 'kind': 'payment', 'amount': a, 'payment': pay, 'with': w, 'series': 'monitoring',
            'description': f"{'cash' if pay == 'cash' else 'bank transfer'} with {w}"} for i, d, a, pay, w in tx]
    return cps, txs


def expected_monitoring(svc, cps, txs, limit):
    """Independent check of the monitoring rules (data/rules/monitoring_rules.json)."""
    rule = {r['check']: r for r in MON}
    out = set()
    months = len({t['date'][:7] for t in txs}) or 1
    if sum(t['amount'] for t in txs) / months > rule['volume_above_profile']['factor'] * svc['expected_monthly']:
        out.add('volume_above_profile')
    cash = [t for t in txs if t['payment'] == 'cash']
    if cash and not svc['cash_allowed']:
        out.add('cash_outside_profile')
    near = [t for t in cash if rule['structuring']['band'] * limit <= t['amount'] < limit]
    if any(a['id'] != b['id'] and abs(a['day'] - b['day']) <= rule['structuring']['window_days'] for a in near for b in near):
        out.add('structuring')
    used = {t['with'] for t in txs}
    for c in cps:
        if c['id'] not in used:
            continue
        if c['country'] in HIGH_RISK: out.add('high_risk_country:' + c['name'])
        if c.get('screening_hit'): out.add('sanctions_hit:' + c['name'])
        if c['checks_done'] < c['checks_total']: out.add('kycc_open:' + c['name'])
        for c2 in cps:
            if c2.get('parent') == c['id'] and c2['country'] in rule['indirect_high_risk']['countries']:
                out.add('indirect_high_risk:' + c2['name'])
    return sorted(out)


def office_records(idx, duties_today):
    """The office's own evidence for its periodic duties; some offices are behind (training overdue, risk assessment missing)."""
    recs = []
    for d in duties_today:
        if d == 'NL:duty:risk-assessment' and idx % 4 == 1:
            continue
        dt = '2025-06-01' if (d == 'NL:duty:training' and idx % 3 == 0) else '2026-02-01'
        recs.append({'id': f'R-{d.split(":")[-1]}', 'duty': d, 'date': dt, 'title': f'evidence: {d.split(":")[-1].replace("-", " ")}'})
    return recs


def expected_office(recs, periodic_active, on):
    year_ago = str(int(on[:4]) - 1) + on[4:]
    out = {}
    for d in periodic_active:
        dates = [r['date'] for r in recs if r['duty'] == d and r['date'] <= on]
        out[d] = 'missing' if not dates else 'up to date' if max(dates) >= year_ago else 'overdue'
    return out


def expected_duties(slug, txs, counterparties, on, band='medium'):
    """Independent check of the sector duties: which apply on date `on`, and what each means for this client."""
    prefixes = {p for x in DUTIES['duties'] for p in x['sectors'] if p != '*'} | set(DUTIES['sector_scope'])
    key = max((p for p in prefixes if slug.startswith(p)), key=len, default=None)
    scope = DUTIES['sector_scope'].get(key, {})
    out = {}
    for d in DUTIES['duties']:
        if not ('*' in d['sectors'] or key in d['sectors']) or d['valid_from'] > on or (d['valid_to'] and d['valid_to'] < on):
            continue
        if not d.get('independent') and scope.get('only_duties') and (scope.get('cdd') is False or on > (scope.get('cdd_until') or '9999-12-31') or on < (scope.get('cdd_from') or '0000-01-01')) and d['id'] not in scope['only_duties']:
            out[d['id']] = 'not applicable'; continue
        hit = [t for t in txs if d['amount'] is not None and t['amount'] >= d['amount'] and (not d['tx'] or t['kind'] in d['tx'])
               and d['payment'] in (None, 'any', t['payment'])]
        k = d['kind']
        out[d['id']] = (('not yet' if on < d['from_date'] else 'applies') if k == 'obliged_from' else
                        'applies' if k in ('always', 'periodic', 'scope_limit') else
                        ('CDD required' if hit else 'not triggered') if k == 'threshold' else
                        ('REPORT to FIU-NL' if hit else 'no objective indicator met') if k == 'indicator' else
                        ('VIOLATION' if hit else 'complied with') if k == 'prohibition' else
                        ('in scope' if hit else 'out of scope') if k == 'scope' else
                        ('REPORT hit' if any(p.get('screening_hit') for p in counterparties) else 'no sanctions hit') if k == 'screening' else
                        ('FREEZE' if any(p.get('screening_hit') for p in counterparties) else 'no sanctions hit') if k == 'freeze' else
                        'in scope' if k == 'service_scope' else
                        {'high': 'EDD required', 'low': 'simplified CDD possible'}.get(band, 'standard CDD') if k == 'risk_band' else
                        ('ASK for the customs declaration' if hit else 'not triggered') if k == 'declaration' else '?')
    return out, scope


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    exp = {}
    for idx, s in enumerate(SECTORS):
        key = next(k for k in PLAN if s['slug'].startswith(k))
        all_duties = {d['id']: d for d in DUTIES['duties']}
        today_duties, _scope = expected_duties(s['slug'], [], [], ON)
        periodic = [d for d, v in today_duties.items() if all_duties[d]['kind'] == 'periodic' and v != 'not applicable']
        everything, _ = expected_duties(s['slug'], [], [], '2026-11-13')
        records = office_records(idx, [d for d, v in everything.items() if all_duties[d]['kind'] == 'periodic'])
        limit = 3000 if 'NL:duty:cash-ban' in everything else 10000
        sup = s['aml_supervisor']
        office = {'id': 'OFF-' + s['slug'][:30], 'name': f"Test office: {s['local'] or s['name']}", 'jurisdiction': 'NL', 'fictitious': True,
                  'sector': {'id': s['id'], 'name': s['name'], 'local': s['local'], 'group': 'all', 'status': s.get('status', 'supervised'), 'obliged_from': s.get('obliged_from')},
                  'regulator': {'id': sup['id'], 'short': sup['short'], 'name': sup['name'], 'role': sup['role']},
                  'guidance': {'id': 'GUIDE:' + (s['guidance'][0]['id'] if s['guidance'] else s['slug']), 'title': s['guidance'][0]['title'] if s['guidance'] else '', 'url': s['guidance'][0]['url'] if s['guidance'] else ''},
                  'guidance_all': s['guidance'], 'records': records}
        for n, scen in enumerate(PLAN[key], 1):
            tag = f"T{s['slug'][:3].upper()}{n}"
            lf, desc, ents, rels, extra = scen(tag)
            cid = f"nl-{s['slug'][:24].rstrip('-')}-{n}"
            tk = next((k for k in sorted(TX, key=len, reverse=True) if s['slug'].startswith(k)), None)
            txs = TX[tk][n - 1] if tk else []
            svc = next((v for k, v in SERVICE.items() if s['slug'].startswith(k)), None)
            prof = service_for(s)
            bt, band = business_type(scen, s['slug'])
            subs, mtx = monitoring(tag, n, prof, limit)
            client = {'name': f"Test client {n} of {office['name'][13:]}", 'jurisdiction': 'NL', 'legal_form': lf, 'activity': desc,
                      **({'service': svc, 'service_in_scope': True} if svc else {}), 'service_profile': {**prof, 'name': svc or prof['name']},
                      'business_type': bt, 'risk': {'band': band, 'triggers': ['high_risk'] if band == 'high' else []}, **({'listed': True} if extra.get('listed') else {}),
                      **({k: extra[k] for k in ('participants', 'licensed_manager', 'person') if k in extra})}
            case = {'id': cid, 'fictitious': True, 'institution': office['id'], 'institution_data': office, 'legal_forms_extra': EXTRA_LF, 'scenario': desc,
                    'client': client, 'entities': ents, 'relations': rels,
                    'documents': [{'id': 'D1', 'title': 'Register extract (test)', 'doctype': 'register_extract', 'date': '2026-11-01', 'text': desc},
                                  {'id': 'D2', 'title': 'Statutes (test)', 'doctype': 'constitutional', 'date': '2026-11-01', 'text': 'test'},
                                  {'id': 'D3', 'title': 'Agreement (test)', 'doctype': 'other', 'date': '2026-11-01', 'text': 'test'}],
                    'questions': [], 'signals': [], 'counterparties': extra.get('counterparties', []) + subs, 'transactions': txs + mtx}
            json.dump(case, open(os.path.join(OUT, cid + '.json'), 'w'), ensure_ascii=False, indent=1)
            ubo, fb = expected(lf, ents, rels, extra)
            duties, scope = expected_duties(s['slug'], txs + mtx, extra.get('counterparties', []) + [x for x in subs if not x.get('parent')], ON, band)
            duties = {k: v for k, v in duties.items() if all_duties[k]['level'] == 'client'}   # the client file holds only the KYC duties per client
            no_cdd = not scope.get('cdd', True) or bool(scope.get('cdd_until') and ON > scope['cdd_until']) or bool(scope.get('cdd_from') and ON < scope['cdd_from'])
            if no_cdd or ON > UBO_RULE_UNTIL:
                ubo, fb = {}, []          # no CDD in this sector on that date, or a date after the modelled rule (AMLR from 10 July 2027)          # no customer due diligence in this sector (today), so no UBO question
            mon = expected_monitoring(prof, subs, mtx, limit)
            if no_cdd:     # no CDD, so no ongoing monitoring; only the cash ban still applies (structuring around EUR 3,000)
                mon = [x for x in mon if x == 'structuring'] if today_duties.get('NL:duty:cash-ban') not in (None, 'not applicable') else []
            exp[cid] = {'office': office['name'], 'office_id': office['id'], 'category': s.get('category'), 'supervisor': sup['short'], 'scenario': desc, 'legal_form': lf, 'ubo': ubo, 'fallback': fb,
                        'transactions': [f"{t['id']} {t['kind']} EUR {t['amount']} {t['payment']}" for t in txs], 'duties': duties, 'no_cdd': no_cdd, 'no_rule': ON > UBO_RULE_UNTIL, 'on': ON,
                        'service': client['service_profile'], 'business_type': bt['code'], 'risk_band': band, 'monitoring': mon, 'office_records': expected_office(records, periodic, ON)}
    os.makedirs(os.path.join(HERE, 'tests'), exist_ok=True)
    json.dump(exp, open(os.path.join(HERE, 'tests', 'expected.json'), 'w'), ensure_ascii=False, indent=1)
    fut = sum(1 for x in SECTORS if x.get('status') == 'future')
    noaml = sum(1 for x in SECTORS if x.get('status') == 'no_aml')
    print(f"{len(exp)} test clients for {len(SECTORS)} test offices: {len(SECTORS) - fut - noaml} Wwft sectors, {fut} coming under the AMLR, {noaml} supervised outside the Wwft "
          f"-> data/testcases/, tests/expected.json (answers as of {ON})")


if __name__ == '__main__':
    main()
