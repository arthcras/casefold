// The risk typology: per category its severity, how many listed entities and cases fall in it.
// from: - | yields: RiskCategory
MATCH (x:RiskCategory)
OPTIONAL MATCH (e:Entity)-[:IN_CATEGORY]->(x)
WITH x, count(DISTINCT e) AS entities
OPTIONAL MATCH (k:Source {kind: 'case'})-[:TYPOLOGY]->(x)
RETURN x.id AS id, x.name AS category, x.severity AS severity, x.group AS kind, x.description AS description, entities, count(DISTINCT k) AS cases
ORDER BY CASE x.severity WHEN 'severe' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END, x.group, category
