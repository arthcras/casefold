#!/usr/bin/env python3
"""Reasoning with memory, stored in the graph.

For one case file this runs the three standard checks and writes every answer as a reasoning chain:
    Answer -[:FIRST_STEP]-> Step -[:NEXT]-> Step ...   (observation -> rule -> derived -> conclusion -> decision)
Every step CITES the nodes it rests on (documents, OCR passages, law articles, persons, counterparties), so a reviewer
can walk from a conclusion back to the evidence. No language model is involved: the steps are Cypher results.

Memory in three time scales:
  short  - Session -[:ASKED]-> Ask -[:ANSWERED_BY]-> Answer   one working session, expires after 8 hours
  medium - Episode -[:BASED_ON]-> Answer                      the decision record of this case: outcome and open items
  long   - Pattern                                            an anonymised, reusable lesson (no names, no amounts), proposed
                                                              in the case; after approval (memory.py approve) it moves to the
                                                              shared long-term store memory/longterm.rl, and reason.py tests
                                                              every approved pattern against each case ("seen before").

Client data never leaves the case file. The long-term store only holds approved patterns: a title, an explanation and a
read-only Cypher test.

usage:  python3 casefold/reason.py cases/nl-kalmora.rl
        python3 casefold/reason.py tests/cases/nl-payment-institutions-1.rl --memory memory/longterm.rl
"""
import argparse, hashlib, json, os, sys
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_case import find_relate, HERE
from embed import relate_rows, relate_write

TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')
NOW = datetime.now(timezone.utc)
ISO = lambda d: d.strftime('%Y-%m-%dT%H:%M:%SZ')
OFFSHORE = ['PA', 'VG', 'KY', 'SC', 'BZ', 'AE']
HIGH_RISK = ['IR', 'KP', 'MM', 'RU', 'SY', 'BY']

# ---- the standard checks: each returns (question, answer text, confidence, steps, outcome, open items, proposed patterns) ----

PATTERN_PEP = {
    'id': 'P-undeclared-indirect-pep',
    'title': 'Politically exposed person owns more than 25% indirectly via a company in an offshore centre, and is missing from the UBO declaration',
    'why': 'An offshore intermediary hides the owner; the declaration then lists only the visible shareholder.',
    'action': 'Request a corrected, signed UBO declaration; enhanced due diligence including source of wealth of the PEP; escalate to the MLRO.',
    'test': ("MATCH p = (v:Person {pep:true})-[:OWNS]->{2,3}(c:Client) "
             "WITH v, p, reduce(x = 1.0, r IN relationships(p) | x * r.pct / 100.0) AS share "
             "WHERE share > 0.25 AND any(n IN nodes(p)[1..-1] WHERE n.country IN $offshore) "
             "OPTIONAL MATCH (d:Document)-[:OF_TYPE]->(:DocumentType {key:'ubo_declaration'}) "
             "WITH v, share, d WHERE d IS NULL OR NOT d.text CONTAINS split(v.name, ' ')[1] "
             "RETURN v.id AS hit, round(share * 100, 1) AS value"),
}
PATTERN_STRUCTURING = {
    'id': 'P-structuring-below-cash-limit',
    'title': 'Two or more cash payments just below a cash limit (EUR 3,000 or EUR 10,000) within a week',
    'why': 'Splitting cash payments to stay under a limit is how the cash ban and the CDD and reporting thresholds are avoided; the law counts linked payments together.',
    'action': 'Treat the linked payments as one; check the cash ban and the thresholds on the total, ask the client for an explanation and consider a report to FIU-Nederland.',
    'test': ("MATCH (c:Client)-[:MADE]->(a:Transaction {payment:'cash'}), (c)-[:MADE]->(b:Transaction {payment:'cash'}) "
             "WHERE a.id < b.id AND abs(a.day - b.day) <= 7 AND ((a.amount >= 2550 AND a.amount < 3000 AND b.amount >= 2550 AND b.amount < 3000) "
             "OR (a.amount >= 8500 AND a.amount < 10000 AND b.amount >= 8500 AND b.amount < 10000)) "
             "MATCH (a)-[:WITH]->(k:Counterparty) RETURN DISTINCT k.id AS hit"),
}

PATTERN_KYCC = {
    'id': 'P-high-risk-counterparty-kycc-open',
    'title': 'A counterparty in a high-risk country has money flows with the client, and its KYCC checks are not complete',
    'why': 'Flows to or from high-risk countries need enhanced KYCC before they continue; an open file means unexplained exposure.',
    'action': 'Complete KYCC (identity, ownership, purpose, sanctions screening) before further transactions; consider blocking flows until done.',
    'test': ("MATCH (k:Counterparty)-[:COUNTERPARTY_OF]->(:Client) MATCH (k)-[:LOCATED_IN]->(g:Country) "
             "WHERE g.code IN $high_risk AND k.volume > 0 AND NOT k.kycc_complete "
             "RETURN k.id AS hit, k.volume AS value"),
}


Q03 = os.path.join(HERE, 'queries', '03_beneficial_owners.cypher')
Q16 = os.path.join(HERE, 'queries', '16_sector_duties.cypher')
Q17 = os.path.join(HERE, 'queries', '17_monitoring.cypher')
Q18 = os.path.join(HERE, 'queries', '18_office_compliance.cypher')


def ubo_under(rel, db, on):
    """Query 03 (grounds per legal form) plus, per person, the chains and documents behind it."""
    q = open(Q03, encoding='utf-8').read().replace('$on', "'" + on + "'").strip().rstrip(';')
    rows = relate_rows(rel, db, q)
    ev = {r['name']: r for r in relate_rows(rel, db, """
MATCH (c:Client) MATCH (o:Person) WHERE EXISTS { (o)-[:OWNS|BOARD_OF|CONTROLS]->{1,5}(c) } OR EXISTS { (o)-[:CONTROLS]->(x) WHERE x = c OR EXISTS { (x)-[:OWNS]->{1,4}(c) } }
OPTIONAL MATCH p = (o)-[:OWNS|BOARD_OF]->{1,5}(c)
OPTIONAL MATCH (o)-[k:CONTROLS]->()
RETURN o.name AS name, o.id AS person, collect(DISTINCT [n IN nodes(p)[1..-1] | {id: n.id, name: n.name, country: n.country}]) AS chains,
       collect(DISTINCT [r IN relationships(p) | r.source]) + collect(DISTINCT [k.source]) AS srcs, collect(DISTINCT k.basis) AS control_basis""")}
    rule = relate_rows(rel, db, """MATCH (:Client)-[:CLIENT_OF]->(:Institution)-[:FOLLOWS]->(u:UboRule) WHERE u.valid_from <= '%s' AND (u.valid_to IS NULL OR u.valid_to >= '%s')
OPTIONAL MATCH (u)-[:DEFINED_IN]->(a:Article) OPTIONAL MATCH (u)-[:HAS_GROUND]->(g:UboGround)
RETURN u.id AS rule, u.name AS rule_name, u.op AS op, u.threshold AS thr, u.method AS method, u.verify AS rule_verify, u.fallback AS fallback,
       collect(DISTINCT a.id) AS arts, collect(DISTINCT g.id) AS grounds""" % (on, on))
    decl = [d['id'] for d in relate_rows(rel, db, "MATCH (d:Document)-[:OF_TYPE]->(t:DocumentType) WHERE t.key IN ['ubo_declaration', 'ubo_register_extract'] RETURN d.id AS id")]
    for r in rows:
        e = ev.get(r['person'], {})
        r.update({'name': r['person'], 'person': e.get('person'), 'chains': [c for c in e.get('chains', []) if c], 'srcs': e.get('srcs', []),
                  'control_basis': [b for b in e.get('control_basis', []) if b], 'declared': r['declaration'] == 'declared',
                  'decl_docs': decl})
    return rows, (rule[0] if rule else None)


def check_ubo(rel, db):
    sc = relate_rows(rel, db, "MATCH (:Client)-[:CLIENT_OF]->(:Institution)-[:IN_SECTOR]->(s:Sector) RETURN s.id AS id, s.cdd AS cdd, s.cdd_until AS until, s.cdd_from AS since, s.scope_note AS note")
    if sc and (sc[0]['cdd'] is False or (sc[0]['until'] and TODAY > sc[0]['until']) or (sc[0]['since'] and TODAY < sc[0]['since'])):
        duty = relate_rows(rel, db, "MATCH (:Sector)-[:HAS_DUTY]->(d:SectorDuty)-[:DEFINED_IN]->(a:Article) WHERE d.kind IN ['scope_limit', 'obliged_from'] RETURN d.id AS d, a.id AS a")
        steps = [('rule', sc[0]['note'], 0.85, [('Sector', sc[0]['id'])] + [('SectorDuty', x['d']) for x in duty] + [('Article', x['a']) for x in duty]),
                 ('conclusion', 'No customer due diligence in this sector today (or not yet), so no UBO question', 0.85, [])]
        return 'Who are the beneficial owners, and does the UBO declaration match?', 'Not applicable: ' + sc[0]['note'], 0.85, steps, 'ok', [], []
    if relate_rows(rel, db, "MATCH (c:Client {natural_person:true}) RETURN c.id AS id"):
        return 'Who are the beneficial owners, and does the UBO declaration match?', 'Not applicable: the client is a natural person', 0.95, [('observation', 'The client is a natural person; there is no UBO to identify', 0.95, [])], 'ok', [], []
    rows, r0 = ubo_under(rel, db, TODAY)
    if not r0:
        return 'Who are the beneficial owners, and does the UBO declaration match?', 'No UBO rule applies to this office', 0.5, [], 'review', [], []
    steps, patterns, open_items = [], [], []
    for r in rows:
        via = r['chains'][0] if r['chains'] else []
        parts = [f"ownership interest {r['ownership']}%", f"votes {r['votes']}%"] + ([f"control via other means ({'; '.join(r['control_basis'])})"] if r['control_basis'] else [])
        steps.append(('observation', f"{r['name']}: " + ', '.join(parts) + (f" through {', '.join(v['name'] + ' (' + v['country'] + ')' for v in via)}" if via else '')
                      + ('; politically exposed person' if r['pep'] else ''), 0.95,
                      [('Party', r['person'])] + [('Party', v['id']) for c in r['chains'] for v in c] + [('Document', s) for ss in r['srcs'] for s in (ss or []) if s]))
    op = {'>': 'more than', '>=': 'at least'}.get(r0['op'], 'no fixed')
    steps.append(('rule', f"Rule this office follows ({r0['rule_name']}), ground by ground for the client's legal form: ownership interest or votes of {op} {r0['thr']}%, or control via other means (no percentage); fallback: {r0['fallback'] or 'not stated'}"
                  + (' (rule to verify)' if r0['rule_verify'] else ''), 0.75 if r0['rule_verify'] else 0.9, [('UboRule', r0['rule'])] + [('UboGround', g) for g in r0['grounds']] + [('Article', a) for a in r0['arts']]))
    ubos = [r for r in rows if r['ubo']]
    steps.append(('derived', 'Beneficial owners under this rule: ' + '; '.join(f"{r['name']} ({', '.join(g.split(': ')[1] for g in r['grounds_met'])})" for r in ubos), 0.9, [('Party', r['person']) for r in ubos]))
    decl_docs = sorted({d for r in rows for d in r['decl_docs']})
    missing = [r for r in ubos if not r['declared']]
    pep = any(r['pep'] for r in missing)
    if not decl_docs:
        steps.append(('conclusion', 'There is no UBO declaration or UBO register extract in the file; ' + ', '.join(r['name'] for r in ubos) + ' must be declared', 0.9, [('Party', r['person']) for r in ubos]))
        steps.append(('decision', 'Proposed: request a signed UBO declaration and, where a UBO register exists, an extract', 0.85, []))
        open_items += ['UBO declaration']
        text, conf, outcome = steps[-2][1], 0.9, 'request documents'
    elif missing:
        steps.append(('conclusion', 'The UBO declaration is incomplete: ' + ', '.join(f"{r['name']} ({', '.join(g.split(': ')[1] for g in r['grounds_met'])}{', PEP' if r['pep'] else ''})" for r in missing) + ' not declared', 0.85,
                      [('Party', r['person']) for r in missing] + [('Document', d) for d in decl_docs]))
        steps.append(('decision', 'Proposed: request a corrected and signed UBO declaration' + ('; enhanced due diligence on the PEP including source of wealth; escalate to the MLRO' if pep else ''), 0.8, []))
        open_items += [f"Corrected UBO declaration ({', '.join(r['name'] for r in missing)})"] + (['Source of wealth of the PEP', 'MLRO escalation'] if pep else [])
        if pep and any(v['country'] in OFFSHORE for r in missing for c in r['chains'] for v in c):
            patterns.append(PATTERN_PEP)
        text, conf, outcome = steps[-2][1], 0.85, 'escalate' if pep else 'request documents'
    else:
        steps.append(('conclusion', 'The UBO declaration matches the ownership chain under the rule that applies today', 0.85, [('Document', d) for d in decl_docs]))
        text, conf, outcome = steps[-1][1], 0.85, 'ok'
    # a rule that takes effect later (if one is in the case file): does it change who is a UBO?
    later = relate_rows(rel, db, "MATCH (:Institution)-[:FOLLOWS]->(u:UboRule) WHERE u.valid_from > '" + TODAY + "' RETURN u.id AS id, u.name AS name, u.valid_from AS valid_from ORDER BY valid_from")
    for f in later:
        fut, _ = ubo_under(rel, db, f['valid_from'])
        now_set = {r['name'] for r in ubos}; fut_set = {r['name'] for r in fut if r['ubo']}
        if now_set != fut_set:
            add, drop = sorted(fut_set - now_set), sorted(now_set - fut_set)
            undecl = [r['name'] for r in fut if r['ubo'] and not r['declared']]
            steps.append(('derived', f"From {f['valid_from']} the rule {f['name']} applies: " + '; '.join(([f"new UBO: {', '.join(add)}"] if add else []) + ([f"no longer UBO: {', '.join(drop)}"] if drop else []))
                          + (f"; then not declared: {', '.join(undecl)}" if undecl else ''), 0.7, [('UboRule', f['id'])] + [('Party', r['person']) for r in fut if r['name'] in fut_set ^ now_set]))
            open_items.append(f"Re-assess the UBOs before {f['valid_from']} ({f['name']})")
            if outcome == 'ok':
                outcome = 'review'
                text = text + f"; from {f['valid_from']} the UBOs change ({', '.join(add + drop)})"
    return 'Who are the beneficial owners, and does the UBO declaration match?', text, conf, steps, outcome, open_items, patterns


def check_missing(rel, db):
    rows = relate_rows(rel, db, """
MATCH (c:Client)-[q:REQUIRES]->(t:DocumentType) WHERE NOT EXISTS { (:Document)-[:OF_TYPE]->(t) }
MATCH (c)-[:CLIENT_OF]->(:Institution)-[:IN_SECTOR]->(sec:Sector) WHERE coalesce(sec.cdd, true) AND (sec.cdd_until IS NULL OR sec.cdd_until >= '%s') AND (sec.cdd_from IS NULL OR sec.cdd_from <= '%s')
OPTIONAL MATCH (c)-[:HAS_LEGAL_FORM]->(f:LegalForm)-[:REQUIRES_DOC]->(t)
OPTIONAL MATCH (c)-[:SUBJECT_TO]->(o:Obligation)-[:PROVEN_BY]->(t) OPTIONAL MATCH (a:Article)-[:IMPOSES]->(o)
OPTIONAL MATCH (c)-[:HAS_TRIGGER]->(g:RiskTrigger)-[:ADDS_REQUIREMENT]->(t)
RETURN t.key AS key, t.name AS name, f.id AS lf, collect(DISTINCT a.id)[0..2] AS arts, collect(DISTINCT a.verify) AS verify, collect(DISTINCT g.key) AS trig
ORDER BY name""" % (TODAY, TODAY))
    if not rows:
        return None
    steps = [('observation', f"{len(rows)} required document types have no document in the file", 0.95, [('DocumentType', r['key']) for r in rows])]
    for r in rows:
        basis = ([f"legal form"] if r['lf'] else []) + ([f"law ({'checked' if False in r['verify'] else 'to verify'})"] if r['arts'] else []) + ([f"risk: {', '.join(r['trig'])}"] if r['trig'] else [])
        steps.append(('rule', f"{r['name'].split(' (')[0]} is required by: {'; '.join(basis)}", 0.9 if False in r['verify'] else 0.75,
                      [('DocumentType', r['key'])] + [('Article', a) for a in r['arts']] + ([('LegalForm', r['lf'])] if r['lf'] else [])))
    steps.append(('decision', 'Proposed: send the client a document request for the missing items; onboarding stays pending until they are in', 0.85, []))
    text = f"{len(rows)} document types missing: " + ', '.join(r['name'].split(' (')[0] for r in rows)
    return 'Which documents are still missing, and on what basis?', text, 0.85, steps, 'request documents' if rows else 'ok', [r['name'].split(' (')[0] for r in rows], []


def check_kycc(rel, db):
    rows = relate_rows(rel, db, """
MATCH (k:Counterparty)-[:COUNTERPARTY_OF]->(:Client) MATCH (k)-[:LOCATED_IN]->(g:Country)
OPTIONAL MATCH (k)-[:SCREENING_HIT]->(h:ScreeningHit)
RETURN k.id AS id, k.name AS name, g.code AS country, k.volume AS volume, k.kycc_level AS level, k.kycc_complete AS complete,
       g.code IN $hr OR g.high_risk AS high_risk, g.code IN $off OR g.offshore AS offshore, h.id AS hit, h.score AS score
ORDER BY volume DESC""".replace('$hr', json.dumps(HIGH_RISK)).replace('$off', json.dumps(OFFSHORE)))
    if not rows:
        return None
    risky = [r for r in rows if (r['high_risk'] or r['offshore'] or r['hit']) and not r['complete']]
    steps = [('observation', f"{len(rows)} counterparties; {sum(1 for r in rows if not r['complete'] and r['level'] != 'none')} with KYCC open", 0.95, [('Counterparty', r['id']) for r in rows])]
    for r in risky:
        steps.append(('observation', f"{r['name']}: {r['country']}{' (high-risk country)' if r['high_risk'] else ' (offshore centre)' if r['offshore'] else ''}, volume {r['volume']:,}, KYCC {r['level']} not complete"
                      + (f", sanctions screening hit {r['score']}%" if r['hit'] else ''), 0.9, [('Counterparty', r['id'])] + ([('ScreeningHit', r['hit'])] if r['hit'] else [])))
    steps.append(('rule', 'Counterparties in high-risk countries, offshore centres or with a screening hit need full KYCC before flows continue', 0.8, []))
    if risky:
        steps.append(('conclusion', f"{len(risky)} risky counterpart{'y' if len(risky) == 1 else 'ies'} without complete KYCC" + ('; a possible sanctions match needs to be resolved first' if any(r['hit'] for r in risky) else ''), 0.85, [('Counterparty', r['id']) for r in risky]))
        steps.append(('decision', 'Proposed: complete KYCC for these counterparties; hold payments to the counterparty with the sanctions hit until the match is cleared', 0.8, []))
    patterns = [PATTERN_KYCC] if any(r['high_risk'] and r['volume'] for r in risky) else []
    return ('Which customers of the client still need KYCC, and which are risky?', steps[-2][1] if risky else 'No risky counterparties with open KYCC', 0.85, steps,
            'hold payments' if any(r['hit'] for r in risky) else ('complete KYCC' if risky else 'ok'), [f"KYCC {r['name']}" for r in risky], patterns)


def check_duties(rel, db):
    """The other duties of the office's sector (question 16): which need action for this client, on which transaction, under which passage."""
    q = open(Q16, encoding='utf-8').read().replace('$on', "'" + TODAY + "'").strip().rstrip(';')
    rows = relate_rows(rel, db, q)
    if not rows:
        return None
    arts = {r['d']: r['a'] for r in relate_rows(rel, db, "MATCH (d:SectorDuty)-[:DEFINED_IN]->(a:Article) RETURN d.id AS d, collect(a.id) AS a")}
    txs = {r['id'] for r in relate_rows(rel, db, "MATCH (:Client)-[:MADE]->(t:Transaction) RETURN t.id AS id")}
    act = [r for r in rows if r['status'].split(':')[0] in ('VIOLATION', 'REPORT to FIU-NL', 'CDD required', 'FREEZE', 'EDD required', 'ASK for the customs declaration') or r['status'].startswith('REPORT hit')]
    sup = relate_rows(rel, db, "MATCH (g:Regulator)-[:SUPERVISES {aml:true}]->(:Sector) RETURN g.short AS s")
    sup = sup[0]['s'] if sup else '?'
    steps = [('observation', f"Office supervised by {sup}: {len(rows)} KYC duties per client on {TODAY} "
              f"({sum(r['status'].startswith('not applicable') for r in rows)} not applicable; the office's own duties are in the office file)", 0.95,
              [('SectorDuty', r['duty_id']) for r in rows])]
    for r in act:
        cited = [t for t in txs if (t + ' ') in r['status']]
        steps.append(('rule', f"{r['duty']} ({'; '.join(r['basis'])})" + (' (to verify)' if r['to_verify'] else ''), 0.75 if r['to_verify'] else 0.9,
                      [('SectorDuty', r['duty_id'])] + [('Article', a) for a in arts.get(r['duty_id'], [])]))
        steps.append(('derived', r['status'], 0.9, [('Transaction', t) for t in cited]))
    if act:
        steps.append(('conclusion', f"{len(act)} sector dut{'y needs' if len(act) == 1 else 'ies need'} action: " + '; '.join(r['status'] for r in act), 0.85, []))
        viol = [r for r in act if r['status'].startswith('VIOLATION')]
        rep = [r for r in act if r['status'].startswith('REPORT')]
        steps.append(('decision', 'Proposed: ' + '; '.join(x for x in (
            'record the cash-ban violation and consider a report to FIU-Nederland' if viol else '',
            'report to FIU-Nederland or the supervisor as stated' if rep else '',
            'complete customer due diligence before the transaction is carried out' if any(r['status'].startswith('CDD') for r in act) else '') if x), 0.8, []))
    text = steps[-2][1] if act else f"No sector duty needs action for this client ({len(rows)} duties apply or were checked)"
    outcome = 'escalate' if any(r['status'].startswith('VIOLATION') for r in act) else 'review' if act else 'ok'
    return 'Which other duties of the sector apply, and which need action?', text, 0.85, steps, outcome, [r['duty'] for r in act], []


def check_monitoring(rel, db):
    """Question 17: the client's transactions with its sub-clients, against the expected profile of the service."""
    rows = relate_rows(rel, db, open(Q17, encoding='utf-8').read().replace('$on', "'" + TODAY + "'").strip().rstrip(';'))
    if not rows:
        return None
    arts = {r['m']: r['a'] for r in relate_rows(rel, db, "MATCH (m:MonitoringRule)-[:DEFINED_IN]->(a:Article) RETURN m.id AS m, collect(a.id) AS a")}
    subs = relate_rows(rel, db, "MATCH (:Client)-[:MADE]->(t:Transaction {series:'monitoring'}) OPTIONAL MATCH (t)-[:WITH]->(k:Counterparty) "
                                "RETURN t.id AS t, k.id AS k, k.name AS name")
    svc = relate_rows(rel, db, "MATCH (:Client)-[:USES]->(v:Service) RETURN v.name AS name, v.expected_monthly AS monthly, v.cash_allowed AS cash")[0]
    steps = [('observation', f"Service: {svc['name']}; expected about EUR {svc['monthly']:,} a month, {'cash expected' if svc['cash'] else 'no cash expected'}; "
              f"{len({x['t'] for x in subs})} transactions with {len({x['k'] for x in subs if x['k']})} sub-clients", 0.95,
              [('Service', 'service')] + [('Transaction', x['t']) for x in subs] + [('Counterparty', x['k']) for x in subs if x['k']])]
    flags = [r for r in rows if r['status'].startswith('FLAG')]
    for r in flags:
        tx = [x['t'] for x in subs if (x['t'] + ' ') in r['status']]
        ks = [x['k'] for x in subs if x['name'] and x['name'] in r['status']]
        steps.append(('rule', f"{r['rule']} ({'; '.join(r['basis'])})" + (' (to verify)' if r['to_verify'] else ''), 0.75 if r['to_verify'] else 0.9,
                      [('MonitoringRule', r['rule_id'])] + [('Article', a) for a in arts.get(r['rule_id'], [])]))
        steps.append(('derived', r['status'][6:], 0.9, [('Transaction', t) for t in tx] + [('Counterparty', k) for k in dict.fromkeys(ks)]))
    if flags:
        steps.append(('conclusion', f"{len(flags)} monitoring signal{'s' if len(flags) > 1 else ''}: " + '; '.join(r['check'].replace('_', ' ') for r in flags), 0.85, []))
        steps.append(('decision', 'Proposed: ' + '; '.join(x for x in (
            'block transactions with the sub-client that has a sanctions hit and report the hit' if any(r['check'] == 'sanctions_hit' for r in flags) else '',
            'enhanced due diligence on the flows with the high-risk country' if any(r['check'] == 'high_risk_country' for r in flags) else '',
            'ask the client to explain the cash payments and treat the linked payments as one; consider a report to FIU-Nederland' if any(r['check'] == 'structuring' for r in flags) else '',
            'update the client\'s profile or ask for the source of the extra funds' if any(r['check'] in ('volume_above_profile', 'cash_outside_profile') for r in flags) else '',
            'complete KYCC on the sub-clients' if any(r['check'] == 'kycc_open' for r in flags) else '') if x), 0.8, []))
    patterns = [PATTERN_STRUCTURING] if any(r['check'] == 'structuring' for r in flags) else []
    outcome = 'hold payments' if any(r['check'] == 'sanctions_hit' for r in flags) else 'review' if flags else 'ok'
    text = steps[-2][1] if flags else f"Transactions within the profile of the service ({svc['name']})"
    return 'Do the client\'s transactions match the profile of its service?', text, 0.85, steps, outcome, [r['check'] for r in flags], patterns


def check_office(rel, db):
    """Question 18: the office's own periodic duties, with the evidence on file."""
    rows = relate_rows(rel, db, open(Q18, encoding='utf-8').read().replace('$on', "'" + TODAY + "'").strip().rstrip(';'))
    if not rows:
        return None
    behind = [r for r in rows if r['status'] != 'up to date']
    steps = [('observation', f"{rows[0]['office']} ({rows[0]['supervisor']}): {len(rows)} periodic duties, {len(behind)} not up to date", 0.95,
              [('SectorDuty', r['duty_id']) for r in rows])]
    for r in behind:
        steps.append(('derived', f"{r['duty']}: {r['status'].lower()}" + (f" (latest evidence {r['latest_evidence']})" if r['latest_evidence'] else ''), 0.9, [('SectorDuty', r['duty_id'])]))
    if behind:
        steps.append(('decision', 'Proposed: bring the office\'s own evidence up to date; the supervisor asks for it in its periodic return', 0.8, []))
    text = ('The office is behind on: ' + '; '.join(f"{r['duty']} ({r['status'].lower()})" for r in behind)) if behind else 'The office\'s periodic duties are up to date'
    return 'Is the office itself up to date with its own duties?', text, 0.9, steps, 'review' if behind else 'ok', [r['duty'] for r in behind], []


def check_patterns(rel, db, memory):
    """Long-term memory: test every approved pattern from the shared store against this case."""
    if not memory or not os.path.exists(memory):
        return None
    pats = relate_rows(rel, memory, "MATCH (p:Pattern {status:'approved'}) RETURN p.id AS id, p.title AS title, p.action AS action, p.test AS test, p.seen AS seen ORDER BY id")
    if not pats:
        return None
    steps, hits = [('observation', f"{len(pats)} approved patterns in long-term memory", 1.0, [])], []
    for p in pats:
        q = p['test'].replace('$offshore', json.dumps(OFFSHORE)).replace('$high_risk', json.dumps(HIGH_RISK))
        rows = relate_rows(rel, db, q)
        if rows:
            hits.append(p)
            lab = 'Party' if 'Person' in q else 'Counterparty'
            steps.append(('rule', f"Seen before ({p['id']}, approved, learned in {p['seen'] or 1} earlier case(s)): {p['title']}", 0.8, [(lab, r['hit']) for r in rows]))
            steps.append(('decision', f"Proposed, from memory: {p['action']}", 0.75, []))
    text = f"{len(hits)} of {len(pats)} approved patterns match this case" + (': ' + '; '.join(h['id'] for h in hits) if hits else '')
    return 'Have we seen this situation before?', text, 0.8, steps, 'review' if hits else 'ok', [f"Pattern {h['id']}" for h in hits], []


def write(rel, db, results):
    case = relate_rows(rel, db, "MATCH (k:Case) RETURN k.id AS id")[0]['id']
    sid = 'S-' + NOW.strftime('%Y%m%d%H%M%S')
    answers, steps, cites, patterns = [], [], [], {}
    for n, (question, text, conf, st, outcome, open_items, pats) in enumerate(results, 1):
        aid = f'{sid}-A{n}'
        answers.append({'id': aid, 'question': question, 'text': text, 'confidence': conf, 'outcome': outcome, 'open_items': open_items})
        for i, (kind, t, c, cs) in enumerate(st, 1):
            sid_ = f'{aid}-{i}'
            steps.append({'id': sid_, 'answer': aid, 'order': i, 'kind': kind, 'text': t, 'confidence': c, 'prev': f'{aid}-{i - 1}' if i > 1 else None})
            cites += [{'step': sid_, 'label': l, 'key': k} for l, k in cs if k]
        for p in pats:
            patterns[p['id']] = {**p, 'status': 'proposed'}
    outcomes = [a['outcome'] for a in answers]
    decision = next((o for o in ['hold payments', 'escalate', 'review', 'complete KYCC', 'request documents'] if o in outcomes), 'accept')
    episode = {'id': f'E-{case}-{NOW.strftime("%Y%m%d%H%M%S")}', 'decision': decision, 'summary': ' | '.join(a['text'] for a in answers)[:900],
               'open_items': [x for a in answers for x in a['open_items']], 'created': ISO(NOW)}
    by_label = {}
    for c in cites:
        by_label.setdefault(c['label'], []).append(c)
    script = """
MATCH (k:Case) MERGE (s:Session {id:$sid}) SET s.started=$now, s.expires=$expires, s.kind='short-term', s.analyst='demo' MERGE (k)-[:HAS_SESSION]->(s);
UNWIND $answers AS a MATCH (s:Session {id:$sid}) CREATE (q:Ask {id:a.id + '-q', text:a.question, at:$now}) CREATE (s)-[:ASKED]->(q)
  CREATE (x:Answer {id:a.id, text:a.text, confidence:a.confidence, outcome:a.outcome, open_items:a.open_items, at:$now}) CREATE (q)-[:ANSWERED_BY]->(x);
UNWIND $steps AS st MATCH (a:Answer {id:st.answer}) CREATE (x:Step {id:st.id, ord:st.order, kind:st.kind, text:st.text, confidence:st.confidence}) CREATE (a)-[:HAS_STEP]->(x);
UNWIND [st IN $steps WHERE st.prev IS NULL] AS st MATCH (a:Answer {id:st.answer}), (x:Step {id:st.id}) CREATE (a)-[:FIRST_STEP]->(x);
UNWIND [st IN $steps WHERE st.prev IS NOT NULL] AS st MATCH (p:Step {id:st.prev}), (x:Step {id:st.id}) CREATE (p)-[:NEXT]->(x);
MATCH (k:Case) CREATE (e:Episode {id:$episode.id, kind:'medium-term', decision:$episode.decision, summary:$episode.summary, open_items:$episode.open_items, created:$episode.created}) CREATE (k)-[:HAS_EPISODE]->(e);
UNWIND $answers AS a MATCH (e:Episode {id:$episode.id}), (x:Answer {id:a.id}) CREATE (e)-[:BASED_ON]->(x);
UNWIND $patterns AS p MATCH (k:Case) MERGE (x:Pattern {id:p.id}) ON CREATE SET x.status='proposed', x.kind='long-term' SET x.title=p.title, x.why=p.why, x.action=p.action, x.test=p.test MERGE (k)-[:PROPOSED]->(x);
UNWIND $patterns AS p MATCH (x:Pattern {id:p.id}), (e:Episode {id:$episode.id}) MERGE (x)-[:LEARNED_FROM]->(e)
"""
    for i, (lab, cs) in enumerate(sorted(by_label.items())):
        keyprop = {'DocumentType': 'key', 'Obligation': 'key', 'Country': 'code'}.get(lab, 'id')
        script += f";\nUNWIND $c{i} AS c MATCH (s:Step {{id:c.step}}) MATCH (n:{lab} {{{keyprop}:c.key}}) MERGE (s)-[:CITES]->(n)"
    params = {'sid': sid, 'now': ISO(NOW), 'expires': ISO(NOW + timedelta(hours=8)), 'answers': answers, 'steps': steps, 'episode': episode, 'patterns': list(patterns.values())}
    params.update({f'c{i}': cs for i, (lab, cs) in enumerate(sorted(by_label.items()))})
    relate_write(rel, db, script, params)
    return sid, episode, list(patterns.values())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('case'); ap.add_argument('--memory', default=os.path.join(HERE, 'memory', 'longterm.rl')); ap.add_argument('--relate')
    a = ap.parse_args()
    rel = find_relate(a.relate)
    results = [r for r in (check_ubo(rel, a.case), check_missing(rel, a.case), check_kycc(rel, a.case), check_duties(rel, a.case), check_monitoring(rel, a.case), check_patterns(rel, a.case, a.memory)) if r]
    sid, ep, pats = write(rel, a.case, results)
    print(f"{a.case}: session {sid} (short-term, expires in 8 h) · episode decision: {ep['decision'].upper()}")
    for q, text, conf, steps, outcome, open_items, _ in results:
        print(f"  - {q}\n      {text}  [{len(steps)} reasoning steps, confidence {conf}]")
    known = {h for r in results for h in r[5] if h.startswith('Pattern ')}
    for p in pats:
        if f"Pattern {p['id']}" in known:
            print(f"  {p['id']} is already in long-term memory; to count this case too:  python3 casefold/memory.py approve {a.case} {p['id']}")
        else:
            print(f"  proposed pattern for long-term memory: {p['id']}  ->  python3 casefold/memory.py approve {a.case} {p['id']}")


if __name__ == '__main__':
    main()
