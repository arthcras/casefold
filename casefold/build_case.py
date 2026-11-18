#!/usr/bin/env python3
"""Build one Relate case file per client: cases/<case-id>.rl

A case file holds three connected layers:
  1. the client file      - client, documents, questions they answer, ownership and control (persons, companies, OWNS, DIRECTOR_OF), signals
  2. the rulebook slice   - the client's legal form and its document rules, the law articles of the jurisdiction, the obligations
                            they impose and the document types that prove them (from data/rulebook/<CC>.json, or pulled from Neo4j)
  3. the KYCC network     - the client's own customers, suppliers and payment providers, their countries and screening hits
  4. the institution      - the trust office that serves the client, its sector, its supervisor and the supervisor's guidance
  5. the UBO rule         - how the supervisor where the service is rendered identifies a beneficial owner (threshold,
                            method, fallback, valid dates); the office FOLLOWS it. Each rule carries its valid dates.
and the links that make it useful: Client -[:REQUIRES {basis}]-> DocumentType <-[:OF_TYPE]- Document.

Relate runs embedded through its CLI (no server). Every case is a single .rl file: one client, one file, easy to hand over,
archive or delete, and never mixed with other clients' data.

usage:  python3 casefold/build_case.py data/cases/nl-kalmora.json            # -> cases/nl-kalmora.rl
        python3 casefold/build_case.py data/cases/*.json --relate /path/to/relate
"""
import argparse, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Document types that a risk trigger adds (on top of the legal form and the law)
TRIGGER_DOCS = {'pep': ['source_of_funds', 'source_of_wealth', 'screening_record'], 'high_risk': ['source_of_funds', 'screening_record'],
                'high_risk_country': ['source_of_funds'], 'complex_structure': ['structure_chart', 'ubo_declaration']}
TRIGGER_NAMES = {'pep': 'Politically exposed person', 'high_risk': 'High-risk client', 'high_risk_country': 'High-risk country involved',
                 'complex_structure': 'Complex or opaque structure'}
EXTRA_DOCTYPES = {'source_of_funds': 'Source of funds evidence', 'source_of_wealth': 'Source of wealth evidence', 'screening_record': 'PEP and sanctions screening record',
                  'structure_chart': 'Structure chart', 'ubo_declaration': 'Beneficial owner declaration / ownership chart'}

SCRIPT = """
CREATE FULLTEXT INDEX doc_text IF NOT EXISTS FOR (n:Document) ON EACH [n.title, n.text];
CREATE FULLTEXT INDEX article_text IF NOT EXISTS FOR (n:Article) ON EACH [n.text_en, n.text_local];
MERGE (k:Case {id:$c.id}) SET k.fictitious=$c.fictitious, k.built=$built, k.rulebook=$r.country.code;

// ---- 2. rulebook slice ----
MERGE (j:Jurisdiction {code:$r.country.code}) SET j.name=$r.country.name;
UNWIND $r.doctypes AS t MERGE (x:DocumentType {key:t.key}) SET x.name=t.name, x.scope=t.scope, x.issuer=t.issuer, x.tier=t.tier;
UNWIND $extra AS t MERGE (x:DocumentType {key:t.key}) ON CREATE SET x.name=t.name;
UNWIND $r.laws AS l MATCH (j:Jurisdiction {code:$r.country.code}) MERGE (x:Law {id:l.id}) SET x.short=l.short, x.title=l.title, x.title_local=l.title_local, x.url=l.url, x.issuer=l.issuer, x.sha256=l.sha256, x.file=l.file MERGE (x)-[:OF]->(j);
UNWIND $r.articles AS a MERGE (x:Article {id:a.id}) SET x.ref=a.ref, x.topic=a.topic, x.lang=a.lang, x.text_local=a.text_local, x.text_en=a.text_en, x.en_type=a.en_type, x.source_url=a.source_url, x.verify=a.verify;
UNWIND [a IN $r.articles WHERE a.law IS NOT NULL] AS a MATCH (x:Article {id:a.id}), (l:Law {id:a.law}) MERGE (x)-[:PART_OF]->(l);
UNWIND $r.obligations AS o MERGE (x:Obligation {key:o.key}) SET x.text=o.text;
UNWIND $r.imposes AS i MATCH (a:Article {id:i.article}), (o:Obligation {key:i.obligation}) MERGE (a)-[x:IMPOSES]->(o) SET x.condition=i.condition, x.strength=i.strength, x.quote=i.quote;
UNWIND $r.proven_by AS p MATCH (o:Obligation {key:p.obligation}), (t:DocumentType {key:p.doctype}) MERGE (o)-[:PROVEN_BY]->(t);
UNWIND [f IN $r.legal_forms WHERE f.id = $c.client.legal_form] AS f MERGE (x:LegalForm {id:f.id}) SET x.abbr=f.abbr, x.name=f.name, x.local=f.local, x.ubo_rule=f.ubo_rule, x.register=f.register;
UNWIND [d IN $r.requires_doc WHERE d.legal_form = $c.client.legal_form] AS d MATCH (f:LegalForm {id:d.legal_form}), (t:DocumentType {key:d.doctype}) MERGE (f)-[x:REQUIRES_DOC]->(t) SET x.when=d.when, x.max_age_months=d.max_age_months, x.local=d.local, x.certified=d.certified;
UNWIND $triggers AS g MERGE (x:RiskTrigger {key:g.key}) SET x.name=g.name;
UNWIND $triggers AS g UNWIND g.docs AS k MATCH (x:RiskTrigger {key:g.key}), (t:DocumentType {key:k}) MERGE (x)-[:ADDS_REQUIREMENT]->(t);

// ---- 1. client file ----
MATCH (k:Case), (j:Jurisdiction {code:$r.country.code}) MERGE (c:Client {id:'client'}) SET c.name=$c.client.name, c.listed=coalesce($c.client.listed, false), c.participants=$c.client.participants, c.licensed_manager=coalesce($c.client.licensed_manager, false), c.natural_person=coalesce($c.client.person, false), c.sector=$c.client.sector, c.activity=$c.client.activity, c.risk_band=$c.client.risk.band, c.triggers=$c.client.risk.triggers
  MERGE (k)-[:ABOUT]->(c) MERGE (c)-[:IN_JURISDICTION]->(j);
UNWIND $lfs AS f MERGE (x:LegalForm {id:f.id}) SET x.local=f.local, x.abbr=f.abbr, x.name=coalesce(x.name, f.en), x.en=f.en, x.category=f.category, x.entity_type=f.entity_type,
  x.legal_personality=f.legal_personality, x.law=f.law, x.law_url=f.law_url, x.register=coalesce(x.register, f.registered_in), x.ubo_rule=f.ubo_rule, x.verify=f.verify;
MATCH (c:Client), (f:LegalForm) WHERE f.id = $c.client.legal_form MERGE (c)-[:HAS_LEGAL_FORM]->(f);
MATCH (c:Client), (g:RiskTrigger) MERGE (c)-[:HAS_TRIGGER]->(g);
UNWIND $c.entities AS e MERGE (x:Party {id:e.id}) SET x.kind=e.kind, x.name=e.name, x.country=e.country, x.pep=coalesce(e.pep,false), x.pep_role=e.pep_role, x.listed=coalesce(e.listed,false), x.exchange=e.exchange;
MATCH (x:Party {kind:'Person'}) SET x:Person;
MATCH (x:Party {kind:'Company'}) SET x:Company;
MATCH (x:Party {kind:'Foundation'}) SET x:Foundation;
MATCH (x:Party {kind:'Group'}) SET x:Group;
UNWIND [e IN $c.entities WHERE e.legal_form IS NOT NULL] AS e MATCH (x:Party {id:e.id}), (f:LegalForm {id:e.legal_form}) MERGE (x)-[:HAS_LEGAL_FORM]->(f);
UNWIND $c.documents AS d MATCH (c:Client) MERGE (x:Document {id:d.id}) SET x.title=d.title, x.date=d.date, x.text=d.text, x.signals=coalesce(d.signals,[]) MERGE (c)-[:HAS_DOCUMENT]->(x);
UNWIND $c.documents AS d MATCH (x:Document {id:d.id}), (t:DocumentType {key:d.doctype}) MERGE (x)-[:OF_TYPE]->(t);
UNWIND [r IN $c.relations WHERE r.type = 'OWNS'] AS r MATCH (a:Party {id:r.from}) MATCH (b) WHERE (b:Party AND b.id = r.to) OR (b:Client AND r.to = 'client')
  MERGE (a)-[x:OWNS]->(b) SET x.pct=r.pct, x.votes=coalesce(r.votes, r.pct), x.kind=coalesce(r.kind, 'legal'), x.lender=coalesce(r.lender, false), x.source=r.source, x.where=r.where;
UNWIND [r IN $c.relations WHERE r.type IN ['MEMBER_OF', 'ROLE_IN']] AS r MATCH (a:Party {id:r.from}) MATCH (b:Client) WHERE r.to = 'client'
  FOREACH (_ IN CASE WHEN r.type = 'MEMBER_OF' THEN [1] ELSE [] END | MERGE (a)-[x:MEMBER_OF]->(b) SET x.votes=r.votes, x.source=r.source, x.where=r.where)
  FOREACH (_ IN CASE WHEN r.type = 'ROLE_IN' THEN [1] ELSE [] END | MERGE (a)-[x:ROLE_IN {role:r.role}]->(b) SET x.source=r.source, x.where=r.where);
UNWIND [r IN $c.relations WHERE r.type = 'BOARD_OF'] AS r MATCH (a:Party {id:r.from}) MATCH (b) WHERE (b:Party AND b.id = r.to) OR (b:Client AND r.to = 'client') MERGE (a)-[x:BOARD_OF]->(b) SET x.votes=r.votes, x.source=r.source, x.where=r.where;
UNWIND [r IN $c.relations WHERE r.type = 'CONTROLS'] AS r MATCH (a:Party {id:r.from}) MATCH (b) WHERE (b:Party AND b.id = r.to) OR (b:Client AND r.to = 'client')
  MERGE (a)-[x:CONTROLS]->(b) SET x.basis=r.basis, x.means=r.means, x.source=r.source, x.where=r.where;
UNWIND [r IN $c.relations WHERE r.type = 'DIRECTOR_OF'] AS r MATCH (a:Party {id:r.from}) MATCH (b) WHERE (b:Party AND b.id = r.to) OR (b:Client AND r.to = 'client')
  MERGE (a)-[x:DIRECTOR_OF]->(b) SET x.source=r.source, x.where=r.where;
UNWIND $c.relations AS r MATCH (d:Document {id:r.source}), (a:Party {id:r.from}) MERGE (d)-[:MENTIONS]->(a);
UNWIND $c.questions AS q MATCH (c:Client) MERGE (x:Question {id:q.id}) SET x.text=q.text, x.status=q.status, x.answer=q.answer MERGE (c)-[:HAS_QUESTION]->(x);
UNWIND $c.questions AS q UNWIND q.sources AS s MATCH (x:Question {id:q.id}), (d:Document {id:s.doc}) MERGE (d)-[a:ANSWERS]->(x) SET a.where=s.where;
UNWIND $c.signals AS s MATCH (c:Client) MERGE (x:Signal {id:s.id}) SET x.title=s.title, x.severity=s.severity MERGE (c)-[:RAISES]->(x);
UNWIND $c.signals AS s UNWIND s.about AS a MATCH (x:Signal {id:s.id}) MATCH (t) WHERE (t:Party OR t:Document OR t:Counterparty) AND t.id = a MERGE (x)-[:ABOUT]->(t);

// ---- 3. KYCC network ----
UNWIND $c.counterparties AS p MATCH (c:Client) MERGE (x:Counterparty {id:p.id}) SET x.level=CASE WHEN p.parent IS NULL THEN 1 ELSE 2 END, x.key=p.key, x.name=p.name, x.party_type=p.type, x.role=p.role, x.country=p.country,
  x.incoming=p.incoming, x.outgoing=p.outgoing, x.volume=p.incoming + p.outgoing, x.transactions=p.transactions, x.kycc_level=p.kycc_level,
  x.checks_done=p.checks_done, x.checks_total=p.checks_total, x.kycc_complete=(p.checks_done >= p.checks_total)
  FOREACH (_ IN CASE WHEN p.parent IS NULL THEN [1] ELSE [] END | MERGE (x)-[r:COUNTERPARTY_OF]->(c) SET r.role=p.role, r.volume=p.incoming + p.outgoing);
UNWIND [p IN $c.counterparties WHERE p.parent IS NOT NULL] AS p MATCH (x:Counterparty {id:p.id}), (y:Counterparty {id:p.parent}) MERGE (x)-[r:COUNTERPARTY_OF]->(y) SET r.role=p.role;
UNWIND $c.counterparties AS p MATCH (x:Counterparty {id:p.id}) MERGE (g:Country {code:p.country}) SET g.high_risk=coalesce(g.high_risk,false) OR coalesce(p.high_risk,false), g.offshore=coalesce(g.offshore,false) OR coalesce(p.offshore,false) MERGE (x)-[:LOCATED_IN]->(g);
UNWIND [p IN $c.counterparties WHERE p.screening_hit IS NOT NULL] AS p MATCH (x:Counterparty {id:p.id}) MERGE (h:ScreeningHit {id:'hit-' + p.id}) SET h.list=p.screening_hit.list, h.matched=p.screening_hit.matched, h.score=p.screening_hit.score MERGE (x)-[:SCREENING_HIT]->(h);
UNWIND $c.signals AS s UNWIND s.about AS a MATCH (x:Signal {id:s.id}), (t:Counterparty {id:a}) MERGE (x)-[:ABOUT]->(t);

// ---- the links between the layers: what this client must deliver, and why ----
MATCH (c:Client)-[:HAS_LEGAL_FORM]->(f:LegalForm)-[r:REQUIRES_DOC]->(t:DocumentType) WHERE r.when CONTAINS 'always' OR (r.when CONTAINS 'high risk' AND c.risk_band = 'high')
  MERGE (c)-[q:REQUIRES]->(t) SET q.by_legal_form=true;
MATCH (c:Client), (a:Article)-[i:IMPOSES]->(o:Obligation) WHERE i.condition IN $conditions MERGE (c)-[:SUBJECT_TO]->(o);
MATCH (c:Client)-[:SUBJECT_TO]->(o:Obligation)-[:PROVEN_BY]->(t:DocumentType) MERGE (c)-[q:REQUIRES]->(t) SET q.by_law=true;
MATCH (c:Client)-[:HAS_TRIGGER]->(g:RiskTrigger)-[:ADDS_REQUIREMENT]->(t:DocumentType) MERGE (c)-[q:REQUIRES]->(t) SET q.by_risk=true;
MATCH (c:Client)-[:SUBJECT_TO]->(o:Obligation)<-[i:IMPOSES]-(:Article) WHERE i.condition STARTS WITH 'sector:'
  MATCH (o)-[:PROVEN_BY]->(t:DocumentType) MATCH (c)-[q:REQUIRES]->(t) SET q.by_sector=true;

// ---- 4. the institution: who serves the client, in which sector, under which supervisor and guidance ----
MATCH (j:Jurisdiction {code:$r.country.code}) MERGE (i:Institution {id:$i.id}) SET i.name=$i.name, i.fictitious=$i.fictitious, i.sector_group=$i.sector.group
  MERGE (i)-[:IN_JURISDICTION]->(j)
  MERGE (s:Sector {id:$i.sector.id}) SET s.name=$i.sector.name, s.local=$i.sector.local, s.group=$i.sector.group MERGE (i)-[:IN_SECTOR]->(s) MERGE (s)-[:IN_JURISDICTION]->(j)
  MERGE (g:Regulator {id:$i.regulator.id}) SET g.short=$i.regulator.short, g.name=$i.regulator.name MERGE (g)-[x:SUPERVISES]->(s) SET x.aml=true, x.role=$i.regulator.role;
MATCH (c:Client), (i:Institution) MERGE (c)-[:CLIENT_OF]->(i);
MATCH (l:Law {id:$i.guidance.id}), (g:Regulator {id:$i.regulator.id}), (s:Sector {id:$i.sector.id}) MERGE (l)-[:ISSUED_BY]->(g) MERGE (l)-[:APPLIES_TO]->(s);

// ---- 5. the UBO rule(s) of the supervisor in the country where the service is rendered (today's, and any that takes effect later) ----
UNWIND $ubo AS u MERGE (x:UboRule {id:u.id}) SET x.cc=u.cc, x.jurisdiction=u.jurisdiction, x.sector=u.sector, x.group=u.group, x.supervisor=u.supervisor,
  x.threshold=u.threshold, x.op=u.op, x.op_note=u.op_note, x.method=u.method, x.basis=u.basis, x.indirect=u.indirect, x.fallback=u.fallback, x.trusts=u.trusts,
  x.source=u.source, x.kind=u.kind, x.source_url=u.source_url, x.text_read=u.text_read, x.verify=u.verify, x.note=u.note, x.valid_from=u.valid_from, x.valid_to=u.valid_to, x.listed_exempt=u.listed_exempt,
  x.name = u.cc + ' ' + CASE u.op WHEN 'none' THEN 'no fixed %' ELSE u.op + ' ' + toString(u.threshold) + '%' END + CASE WHEN u.group = 'trust' THEN '' ELSE ' (' + u.group + ')' END;
UNWIND $ubo AS u MATCH (x:UboRule {id:u.id}), (j:Jurisdiction {code:$r.country.code}) MERGE (x)-[:APPLIES_IN]->(j);
UNWIND $ubo AS u UNWIND u.grounds AS g MATCH (x:UboRule {id:u.id}) MERGE (y:UboGround {id:g.id}) SET y.entity_type=g.entity, y.ground=g.ground, y.threshold=g.threshold, y.op=g.op, y.note=g.note,
  y.name = g.entity + ': ' + g.ground + CASE WHEN g.op IN ['>', '>='] THEN ' ' + g.op + ' ' + toString(g.threshold) + '%' ELSE '' END MERGE (x)-[:HAS_GROUND]->(y);
UNWIND keys($gt) AS k MERGE (t:GroundType {key:k}) SET t.name=$gt[k].name, t.reference=$gt[k].reference;
MATCH (y:UboGround), (t:GroundType) WHERE y.ground = t.key MERGE (y)-[:IS_A]->(t);
UNWIND $ubo AS u UNWIND [g IN u.grounds WHERE g.passage IS NOT NULL] AS g MATCH (y:UboGround {id:g.id})
  MERGE (a:Article {id:'ART:' + g.id}) SET a.ref=g.passage.ref, a.topic='UBO ground: ' + g.ground, a.lang='nl', a.text_local=g.passage.text, a.text_en=coalesce(g.passage.text_en, ''), a.en_type=coalesce(g.passage.en_type, 'none'),
    a.source_url=u.source_url, a.verify=false, a.read_on='2026-11-13', a.primary=true
  MERGE (y)-[:DEFINED_IN]->(a)
  WITH a MATCH (l:Law {id:'NL:uitvoeringsbesluit-wwft'}) MERGE (a)-[:PART_OF]->(l);
UNWIND $rule_articles AS m MATCH (x:UboRule {id:m.rule}), (a:Article {id:m.article}) MERGE (x)-[:DEFINED_IN]->(a);
UNWIND [u IN $ubo WHERE u.passage.text <> '' AND NOT u.id IN [m IN $rule_articles | m.rule]] AS u
  MERGE (l:Law {id:'SRC:' + u.id}) SET l.short=u.passage.ref, l.title=u.source, l.url=u.source_url, l.kind=u.kind
  MERGE (a:Article {id:'ART:' + u.id}) SET a.ref=u.passage.ref, a.topic='Ultimate beneficial owner (definition)', a.lang=u.passage.lang,
    a.text_local=CASE WHEN u.passage.lang = 'en' THEN '' ELSE u.passage.text END, a.text_en=CASE WHEN u.passage.lang = 'en' THEN u.passage.text ELSE coalesce(u.passage.text_en, '') END,
    a.en_type=CASE WHEN u.passage.lang = 'en' THEN 'source' ELSE coalesce(u.passage.en_type, 'none') END, a.source_url=u.source_url, a.verify=u.verify, a.read_on=u.passage.read_on, a.primary=u.passage.primary
  MERGE (a)-[:PART_OF]->(l)
  WITH u, a MATCH (x:UboRule {id:u.id}) MERGE (x)-[:DEFINED_IN]->(a);
MATCH (i:Institution)-[:IN_JURISDICTION]->(j:Jurisdiction)<-[:APPLIES_IN]-(u:UboRule) WHERE u.group IN [i.sector_group, 'all']
  MERGE (i)-[f:FOLLOWS]->(u) SET f.valid_from=u.valid_from, f.valid_to=u.valid_to SET u.applies_here=true;
// the office applies its own rule to every entity in the structure, by the legal-entity type of its legal form
MATCH (f:LegalForm) MATCH (:Institution)-[:FOLLOWS]->(:UboRule)-[:HAS_GROUND]->(g:UboGround) WHERE g.entity_type = f.entity_type MERGE (f)-[:TESTED_BY]->(g);

// ---- 6. the other duties of the sector, besides the UBO: from the law and the supervisor, each with the passage it rests on ----
UNWIND $dlaws AS l MERGE (x:Law {id:l.id}) SET x.short=coalesce(x.short, l.short), x.title=coalesce(x.title, l.title), x.url=coalesce(x.url, l.url);
MATCH (s:Sector) SET s.cdd=$scope.cdd, s.cdd_until=$scope.cdd_until, s.cdd_from=$scope.cdd_from, s.status=$i.sector.status, s.obliged_from=$i.sector.obliged_from, s.only_duties=$scope.only_duties, s.scope_note=$scope.note;
UNWIND $duties AS d MATCH (s:Sector) MERGE (x:SectorDuty {id:d.id}) SET x.title=d.title, x.level=d.level, x.kind=d.kind, x.amount=d.amount, x.payment=d.payment, x.tx=d.tx,
  x.frequency=d.frequency, x.from_date=d.from_date, x.authority=d.authority, x.independent=d.independent, x.valid_from=d.valid_from, x.valid_to=d.valid_to, x.search=d.search MERGE (s)-[:HAS_DUTY]->(x);
UNWIND $duties AS d UNWIND range(0, size(d.basis) - 1) AS n WITH d, n, d.basis[n] AS b MATCH (x:SectorDuty {id:d.id}), (l:Law {id:b.law})
  MERGE (a:Article {id:'DUTY:' + d.id + ':' + toString(n)}) SET a.ref=b.ref, a.topic='Sector duty: ' + d.title, a.lang='nl', a.text_local=b.text, a.text_en=coalesce(b.text_en, ''), a.en_type=coalesce(b.en_type, 'none'),
    a.source_url=b.url, a.verify=b.verify, a.basis_kind=b.kind, a.read_in=b.read, a.valid_from=b.valid_from, a.valid_to=b.valid_to, a.regime=b.regime, a.law_short=b.law_short, a.art=b.art, a.lid=b.lid, a.heading=b.heading
  MERGE (x)-[:DEFINED_IN]->(a) MERGE (a)-[:PART_OF]->(l);
UNWIND $duties AS d UNWIND [n IN range(0, size(d.basis) - 1) WHERE d.basis[n].replaces IS NOT NULL] AS n
  MATCH (o:Article {id:'DUTY:' + d.id + ':' + toString(d.basis[n].replaces)}), (a:Article {id:'DUTY:' + d.id + ':' + toString(n)}) MERGE (o)-[:REPLACED_BY]->(a);
UNWIND [d IN $duties WHERE d.replaces IS NOT NULL] AS d MATCH (o:SectorDuty {id:d.replaces}), (x:SectorDuty {id:d.id}) MERGE (o)-[:REPLACED_BY]->(x);
UNWIND [b IN [$c.client.business_type] WHERE b IS NOT NULL] AS b MATCH (c:Client) MERGE (t:BusinessType {code:b.code}) SET t.sbi=b.sbi, t.name=b.name, t.name_nl=b.name_nl
  MERGE (c)-[:HAS_BUSINESS_TYPE]->(t) SET c.risk_factors=[f IN b.factors | f.id + ': ' + f.text]
  WITH b, t UNWIND b.factors AS f MERGE (r:RiskFactor {id:f.id}) SET r.annex=f.annex, r.ref=f.ref, r.text=f.text MERGE (t)-[:HAS_RISK_FACTOR]->(r);
MATCH (c:Client) SET c.service=$c.client.service, c.service_in_scope=coalesce($c.client.service_in_scope, true);
UNWIND $c.transactions AS t MATCH (c:Client) MERGE (x:Transaction {id:t.id}) SET x.date=t.date, x.day=t.day, x.kind=t.kind, x.amount=t.amount, x.currency=coalesce(t.currency, 'EUR'),
  x.payment=t.payment, x.description=t.description, x.series=t.series MERGE (c)-[:MADE]->(x);
UNWIND [t IN $c.transactions WHERE t.with IS NOT NULL] AS t MATCH (x:Transaction {id:t.id}), (k:Counterparty {id:t.with}) MERGE (x)-[:WITH]->(k);
UNWIND [p IN [$c.client.service_profile] WHERE p IS NOT NULL] AS p MATCH (c:Client) MERGE (v:Service {id:'service'}) SET v.name=p.name, v.expected_monthly=p.expected_monthly, v.cash_allowed=p.cash_allowed
  MERGE (c)-[:USES]->(v);
MATCH (c:Client)-[:MADE]->(t:Transaction {series:'monitoring'}), (c)-[:USES]->(v:Service) MERGE (t)-[:UNDER]->(v);
UNWIND $mon AS m MERGE (x:MonitoringRule {id:m.id}) SET x.title=m.title, x.check=m.check, x.factor=m.factor, x.window_days=m.window_days, x.band=m.band, x.countries=m.countries;
UNWIND $mon AS m UNWIND range(0, size(m.basis) - 1) AS n WITH m, n, m.basis[n] AS b MATCH (x:MonitoringRule {id:m.id}), (l:Law {id:b.law})
  MERGE (a:Article {id:m.id + ':' + toString(n)}) SET a.ref=b.ref, a.topic='Monitoring: ' + m.title, a.lang='nl', a.text_local=b.text, a.text_en=coalesce(b.text_en, ''), a.en_type=coalesce(b.en_type, 'none'),
    a.source_url=b.url, a.verify=b.verify, a.basis_kind=b.kind, a.read_in=b.read
  MERGE (x)-[:DEFINED_IN]->(a) MERGE (a)-[:PART_OF]->(l)
"""


def sector_duties(sector):
    """The duties of data/rules/sector_duties.json that apply to this sector. A duty names sector-slug prefixes; a sector takes the
    longest prefix that matches it, so 'banks' does not also select 'banks-and-e-money-...'."""
    d = json.load(open(os.path.join(HERE, 'data', 'rules', 'sector_duties.json'), encoding='utf-8'))
    slug = sector['id'].split(':', 1)[1]
    prefixes = {p for x in d['duties'] for p in x['sectors'] if p != '*'} | set(d['sector_scope'])
    key = max((p for p in prefixes if slug.startswith(p)), key=len, default=None)
    duties = [x for x in d['duties'] if '*' in x['sectors'] or key in x['sectors']]
    scope = {'cdd': True, 'cdd_until': None, 'cdd_from': None, 'only_duties': None, 'note': None} | d['sector_scope'].get(key, {})
    return duties, d['laws'], scope


def sector_class(sector_id):
    """The place of a sector in the classification (data/sector_taxonomy.json): its category and its FATF scope."""
    tax = json.load(open(os.path.join(HERE, 'data', 'sector_taxonomy.json'), encoding='utf-8'))
    sec = next((x for x in json.load(open(os.path.join(HERE, 'data', 'sectors.json'), encoding='utf-8'))['sectors'] if x['id'] == sector_id), {})
    cat = next((c for c in tax['categories'] if c['id'] == sec.get('category')), None)
    scope = next((f for f in tax['scopes'] if f['id'] == sec.get('fatf_scope')), None)
    aml = (sec.get('aml_supervisor') or {}).get('id')
    sups = [{**g, 'aml': g['id'] == aml} for g in sec.get('supervisors') or []] or ([{**sec['aml_supervisor'], 'aml': True}] if sec.get('aml_supervisor') else [])
    duties = json.load(open(os.path.join(HERE, 'data', 'rules', 'sector_duties.json'), encoding='utf-8'))
    for a in duties.get('authorities', []):            # FIU-Nederland, AP, KvK for every sector; ECB for banks; AMLA for FI and VASP
        if ('*' in a.get('sectors', ['*']) or any(sec.get('slug', '') == x[1:] if x.startswith('=') else sec.get('slug', '').startswith(x) for x in a['sectors'])) and (not a.get('fatf') or sec.get('fatf_scope') in a['fatf']) and sec.get('status') not in a.get('status_not', []):
            sups.append({'id': a['id'], 'short': a['short'], 'name': a['name'], 'role': a['role'], 'aml': False})
    L = json.load(open(os.path.join(HERE, 'data', 'rules', 'licences.json'), encoding='utf-8'))
    key = max((k for k in L['licences'] if sec.get('slug', '').startswith(k)), key=len, default=None)
    lic = dict(L['licences'][key], id='LIC:' + key) if key else None
    known = {g['id'] for g in sups} | {'NL:tbd'}
    if lic and lic['kind'] != 'none':
        other = {o['id']: o for o in L['other_authorities']}
        if lic['authority'] in known:
            for g in sups:
                if g['id'] == lic['authority'] and 'licens' not in (g.get('role') or ''):
                    g['role'] = (g.get('role') or '') + '+licensing'
        elif lic['authority'] in other:
            sups.append({**other[lic['authority']], 'role': 'licensing', 'aml': False})
    LW = json.load(open(os.path.join(HERE, 'data', 'rules', 'laws.json'), encoding='utf-8'))
    mine = {a['law']: a['source'] for a in LW['applies'] if a['sector'] == sector_id}
    laws = [{**l, 'source': mine[l['id']]} for l in LW['laws'] if l['id'] in mine]
    return {'laws': laws, 'licence': lic, 'supervisors': sups, 'jurisdiction': sector_id.split(':')[0], 'expected_supervisor': sec.get('expected_supervisor'),
            'category': {k: cat[k] for k in ('id', 'name', 'name_nl')} if cat else None,
            'scope': {**{k: scope[k] for k in ('id', 'name', 'name_nl')}, 'source': sec.get('fatf_source')} if scope else None}


CLASS_SCRIPT = """
UNWIND $cls.supervisors AS g MATCH (s:Sector) MERGE (r:Regulator {id:g.id}) SET r.short=coalesce(r.short, g.short), r.name=coalesce(r.name, g.name)
  MERGE (r)-[x:SUPERVISES]->(s) SET x.role=g.role, x.aml=coalesce(x.aml, false) OR g.aml;
MATCH (s:Sector) SET s.expected_supervisor=$cls.expected_supervisor;
UNWIND $cls.laws AS l MATCH (s:Sector) MERGE (x:Law {id:l.id}) SET x.short=coalesce(x.short, l.short), x.title=coalesce(x.title, l.title), x.url=coalesce(x.url, l.url), x.kind=l.kind, x.valid_from=l.valid_from, x.scope=l.note
  MERGE (s)-[r:SUBJECT_TO]->(x) SET r.source=l.source;
UNWIND [x IN [$cls.licence] WHERE x IS NOT NULL] AS l MATCH (s:Sector) MERGE (x:Licence {id:l.id}) SET x.kind=l.kind, x.name=l.name, x.basis=l.basis, x.url=l.url, x.verify=l.verify, x.note=l.note
  MERGE (s)-[:REQUIRES_LICENCE]->(x)
  WITH x, l MATCH (r:Regulator {id:l.authority}) MERGE (x)-[:GRANTED_BY]->(r);
MATCH (i:Institution)-[:IN_SECTOR]->(:Sector)-[:REQUIRES_LICENCE]->(x:Licence) WHERE x.kind <> 'none' AND coalesce(i.fictitious, true) MERGE (i)-[h:HOLDS]->(x) SET h.number='TEST-' + toUpper(substring(x.id, 4, 6)), h.fictitious=true;
UNWIND [x IN [$cls.category] WHERE x IS NOT NULL] AS c MATCH (s:Sector) MERGE (k:SectorCategory {id:c.id}) SET k.name=c.name, k.name_nl=c.name_nl MERGE (s)-[:IN_CATEGORY]->(k);
UNWIND [x IN [$cls.scope] WHERE x IS NOT NULL] AS f MATCH (s:Sector) MERGE (k:FatfScope {id:f.id}) SET k.name=f.name, k.name_nl=f.name_nl MERGE (s)-[r:IN_SCOPE]->(k) SET r.source=f.source
"""


def find_relate(cli):
    for c in [cli, os.environ.get('RELATE_BIN'), shutil.which('relate'), os.path.expanduser('~/.local/bin/relate')]:
        if c and os.path.exists(c):
            return c
    sys.exit('Relate not found. Install it with:  curl -sSfL https://relatedb.ai/install.sh | bash   (or pass --relate PATH)')


def run(relate, db, params, script=None, command=None, read=False):
    args, tmp = [relate, 'query', '--database', db], []
    try:
        for k, v in params.items():
            fd, p = tempfile.mkstemp(suffix='.json'); os.close(fd); tmp.append(p)
            json.dump(v, open(p, 'w', encoding='utf-8'), ensure_ascii=False); args += ['--fetch-params', f'{k}={p}']
        if read:
            args += ['--read-only', '--mode', 'json', '--max-rows', '0']
        if command:
            args += ['-c', command]
        r = subprocess.run(args, input=None if command else script, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            sys.exit(f'relate failed:\n{(r.stderr or r.stdout)[-1500:]}')
        if read:
            out = r.stdout; i = out.find('{"data"')
            return json.loads(out[i:])['data'] if i >= 0 else []
    finally:
        for p in tmp:
            os.remove(p)


RULE_ARTICLES = [{'rule': 'UBO:NL:wwft', 'article': 'NL:UBW:3'}]


def build(case_path, relate, out_dir, rulebook_dir, pulled=False):
    """pulled=True: the rulebook slice is already in the case file (relate pull from Neo4j); only the client layers are added."""
    case = json.load(open(case_path, encoding='utf-8'))
    cc = case['client']['jurisdiction']
    rp = os.path.join(rulebook_dir, f'{cc}.json')
    rule = json.load(open(rp, encoding='utf-8')) if os.path.exists(rp) else \
        {'country': {'code': cc, 'name': cc}, **{k: [] for k in ('doctypes', 'laws', 'articles', 'obligations', 'imposes', 'proven_by', 'legal_forms', 'requires_doc')}}
    if pulled:
        rule = {**{k: [] for k in ('doctypes', 'laws', 'articles', 'obligations', 'imposes', 'proven_by', 'legal_forms', 'requires_doc')}, 'country': rule['country']}
    inst = case.get('institution_data') or next(i for i in json.load(open(os.path.join(HERE, 'data', 'institutions.json'), encoding='utf-8'))['institutions'] if i['id'] == case['institution'])
    ubo = [u for u in json.load(open(os.path.join(HERE, 'data', 'rules', 'ubo_rules.json'), encoding='utf-8'))['rules']
           if cc in u['applies_in'] and u['group'] in (inst['sector']['group'], 'all')]   # the rules of the country where the service is rendered
    inv = {f['id']: f for f in json.load(open(os.path.join(HERE, 'data', 'rules', 'legal_forms.json'), encoding='utf-8'))['legal_forms']}
    want = ({case['client']['legal_form']} if case['client'].get('legal_form') else set()) | {e['legal_form'] for e in case.get('entities', []) if e.get('legal_form')}
    lfs = [inv[i] for i in sorted(want) if i in inv] + [x for x in case.get('legal_forms_extra', []) if x['id'] in want and x['id'] not in inv]
    trig = case['client']['risk'].get('triggers') or []
    band = case['client']['risk'].get('band', 'low')
    conditions = ['always', 'risk_based', 'sector:' + inst['sector']['group']] + trig + (['high_risk'] if band == 'high' else [])
    triggers = [{'key': t, 'name': TRIGGER_NAMES.get(t, t), 'docs': TRIGGER_DOCS.get(t, [])} for t in trig]
    known = {d['key'] for d in rule['doctypes']}
    extra = [{'key': k, 'name': v} for k, v in EXTRA_DOCTYPES.items() if k not in known]
    duties, dlaws, scope = sector_duties(inst['sector'])
    duties = [d for d in duties if d['level'] == 'client']     # the client file holds the KYC duties per client; the office's own duties are in the office file
    for k in ('entities', 'relations', 'documents', 'questions', 'signals', 'counterparties', 'transactions'):
        case.setdefault(k, [])
    for p in case['counterparties']:
        for k, v in (('incoming', 0), ('outgoing', 0), ('transactions', 0), ('checks_done', 0), ('checks_total', 0), ('kycc_level', 'none')):
            p.setdefault(k, v)
    os.makedirs(out_dir, exist_ok=True)
    db = os.path.join(out_dir, case['id'] + '.rl')
    if not pulled and os.path.exists(db):
        shutil.rmtree(db) if os.path.isdir(db) else os.remove(db)
    import clock
    run(relate, db, {'c': case, 'r': rule, 'i': inst, 'ubo': ubo, 'rule_articles': RULE_ARTICLES, 'lfs': lfs, 'gt': json.load(open(os.path.join(HERE, 'data', 'rules', 'ubo_rules.json'), encoding='utf-8'))['ground_types'], 'triggers': triggers, 'duties': duties, 'dlaws': dlaws, 'scope': scope, 'mon': json.load(open(os.path.join(HERE, 'data', 'rules', 'monitoring_rules.json'), encoding='utf-8'))['rules'], 'extra': extra, 'conditions': conditions,
                     'built': clock.stamp()}, script=SCRIPT)
    run(relate, db, {'cls': sector_class(inst['sector']['id'])}, script=CLASS_SCRIPT)
    counts = run(relate, db, {}, command='MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY label', read=True)
    miss = run(relate, db, {}, read=True, command="MATCH (c:Client)-[:REQUIRES]->(t:DocumentType) WHERE NOT EXISTS { (:Document)-[:OF_TYPE]->(t) } RETURN count(t) AS n")
    print(f"{db}: " + ', '.join(f"{r['label']} {r['n']}" for r in counts) + f" | missing document types: {miss[0]['n'] if miss else '?'}")
    return db


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cases', nargs='+', help='case JSON files (data/cases/*.json)')
    ap.add_argument('--relate', help='path to the relate binary')
    ap.add_argument('--out', default=os.path.join(HERE, 'cases'))
    ap.add_argument('--rulebook', default=os.path.join(HERE, 'data', 'rulebook'))
    ap.add_argument('--pulled', action='store_true', help='the case file already holds the rulebook slice pulled from Neo4j (relate pull); add only the client layers')
    a = ap.parse_args()
    relate = find_relate(a.relate)
    for c in a.cases:
        build(c, relate, a.out, a.rulebook, pulled=a.pulled)


if __name__ == '__main__':
    main()
