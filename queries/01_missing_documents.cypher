// Which documents does this client still have to deliver, and on what basis?
// Only where the office's sector requires customer due diligence on $on (not for traders in goods from 2026, nor for appraisers).
// For every required document type that no document in the file proves: the legal form rule, the law article (with the quote) or the risk trigger behind it.
MATCH (c:Client)-[q:REQUIRES]->(t:DocumentType)
WHERE NOT EXISTS { (:Document)-[:OF_TYPE]->(t) }
MATCH (c)-[:CLIENT_OF]->(:Institution)-[:IN_SECTOR]->(sec:Sector) WHERE coalesce(sec.cdd, true) AND (sec.cdd_until IS NULL OR sec.cdd_until >= $on) AND (sec.cdd_from IS NULL OR sec.cdd_from <= $on)
OPTIONAL MATCH (c)-[:HAS_LEGAL_FORM]->(f:LegalForm)-[ld:REQUIRES_DOC]->(t)
OPTIONAL MATCH (c)-[:SUBJECT_TO]->(o:Obligation)-[:PROVEN_BY]->(t)
OPTIONAL MATCH (a:Article)-[i:IMPOSES]->(o)
OPTIONAL MATCH (c)-[:HAS_TRIGGER]->(g:RiskTrigger)-[:ADDS_REQUIREMENT]->(t)
RETURN t.name AS missing_document,
       collect(DISTINCT CASE WHEN f IS NULL THEN null ELSE f.abbr + ': ' + coalesce(ld.local, ld.when) END) AS legal_form_rule,
       collect(DISTINCT a.ref + CASE WHEN a.verify THEN ' (to verify)' ELSE ' (checked)' END) AS law_articles,
       collect(DISTINCT g.name) AS risk_triggers
ORDER BY missing_document;
