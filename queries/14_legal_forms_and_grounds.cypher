// Every entity in the structure, its legal form, and the grounds on which its beneficial owners are determined (from the legal-form inventory and the UBO rule of the office)
MATCH (x) WHERE (x:Client OR x:Party) AND EXISTS { (x)-[:HAS_LEGAL_FORM]->() }
MATCH (x)-[:HAS_LEGAL_FORM]->(f:LegalForm)
OPTIONAL MATCH (f)-[:TESTED_BY]->(g:UboGround)
RETURN x:Client AS client, x.name AS entity, f.abbr + ' (' + split(f.id, ':')[0] + ')' AS legal_form, f.category AS category, f.entity_type AS tested_as,
       collect(g.ground + CASE WHEN g.op IN ['>', '>='] THEN ' ' + g.op + ' ' + toString(g.threshold) + '%' ELSE '' END) AS grounds_here,
       f.ubo_rule AS ubo_rule_for_this_form, f.law AS law, CASE WHEN f.verify THEN 'to verify' ELSE 'checked' END AS status
ORDER BY client DESC, entity;
