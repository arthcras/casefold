#!/usr/bin/env python3
"""Write neo4j/rulebook.cypher: the rulebook slices (data/rulebook/*.json) as Cypher for a central Neo4j.
This plays the role of the central regulatory graph; each case file later pulls only its own slice from it (neo4j/pull_rulebook.cypher).

usage:  python3 casefold/rulebook_to_cypher.py > neo4j/rulebook.cypher
"""
import glob, json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
q = lambda v: json.dumps(v, ensure_ascii=False)
print('// Generated from data/rulebook/*.json by casefold/rulebook_to_cypher.py')
for c in ['CREATE CONSTRAINT IF NOT EXISTS FOR (n:Jurisdiction) REQUIRE n.code IS UNIQUE', 'CREATE CONSTRAINT IF NOT EXISTS FOR (n:Law) REQUIRE n.id IS UNIQUE',
          'CREATE CONSTRAINT IF NOT EXISTS FOR (n:Article) REQUIRE n.id IS UNIQUE', 'CREATE CONSTRAINT IF NOT EXISTS FOR (n:Obligation) REQUIRE n.key IS UNIQUE',
          'CREATE CONSTRAINT IF NOT EXISTS FOR (n:DocumentType) REQUIRE n.key IS UNIQUE', 'CREATE CONSTRAINT IF NOT EXISTS FOR (n:LegalForm) REQUIRE n.id IS UNIQUE']:
    print(c + ';')
for f in sorted(glob.glob(os.path.join(HERE, 'data', 'rulebook', '*.json'))):
    r = json.load(open(f, encoding='utf-8')); cc = r['country']['code']
    print(f"MERGE (j:Jurisdiction {{code:{q(cc)}}}) SET j.name={q(r['country']['name'])};")
    for t in r['doctypes']:
        print(f"MERGE (x:DocumentType {{key:{q(t['key'])}}}) SET x.name={q(t['name'])}, x.scope={q(t['scope'])}, x.issuer={q(t['issuer'])}, x.tier={t['tier']};")
    for l in r['laws']:
        print(f"MATCH (j:Jurisdiction {{code:{q(cc)}}}) MERGE (x:Law {{id:{q(l['id'])}}}) SET x.short={q(l['short'])}, x.title={q(l['title'])}, x.title_local={q(l['title_local'])}, x.url={q(l['url'])} MERGE (x)-[:OF]->(j);")
    for a in r['articles']:
        print(f"MERGE (x:Article {{id:{q(a['id'])}}}) SET x.jurisdiction={q(cc)}, x.ref={q(a['ref'])}, x.topic={q(a['topic'])}, x.lang={q(a['lang'])}, x.text_local={q(a['text_local'])}, x.text_en={q(a['text_en'])}, x.en_type={q(a['en_type'])}, x.source_url={q(a['source_url'])}, x.verify={q(a['verify'])};")
        if a['law']:
            print(f"MATCH (x:Article {{id:{q(a['id'])}}}), (l:Law {{id:{q(a['law'])}}}) MERGE (x)-[:PART_OF]->(l);")
    for o in r['obligations']:
        print(f"MERGE (x:Obligation {{key:{q(o['key'])}}}) SET x.text={q(o['text'])};")
    for i in r['imposes']:
        print(f"MATCH (a:Article {{id:{q(i['article'])}}}), (o:Obligation {{key:{q(i['obligation'])}}}) MERGE (a)-[x:IMPOSES]->(o) SET x.condition={q(i['condition'])}, x.strength={q(i['strength'])}, x.quote={q(i['quote'])};")
    for p in r['proven_by']:
        print(f"MATCH (o:Obligation {{key:{q(p['obligation'])}}}), (t:DocumentType {{key:{q(p['doctype'])}}}) MERGE (o)-[:PROVEN_BY]->(t);")
    for lf in r['legal_forms']:
        print(f"MATCH (j:Jurisdiction {{code:{q(cc)}}}) MERGE (x:LegalForm {{id:{q(lf['id'])}}}) SET x.abbr={q(lf['abbr'])}, x.name={q(lf['name'])}, x.local={q(lf['local'])}, x.ubo_rule={q(lf['ubo_rule'])}, x.register={q(lf['register'])} MERGE (x)-[:IN]->(j);")
    for d in r['requires_doc']:
        print(f"MATCH (f:LegalForm {{id:{q(d['legal_form'])}}}), (t:DocumentType {{key:{q(d['doctype'])}}}) MERGE (f)-[x:REQUIRES_DOC]->(t) SET x.when={q(d['when'])}, x.max_age_months={q(d['max_age_months'])}, x.local={q(d['local'])}, x.certified={q(d['certified'])};")
