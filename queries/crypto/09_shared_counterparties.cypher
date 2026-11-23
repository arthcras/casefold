// Counterparties that dealt with the addresses of two different listed entities (for example Garantex and Grinex).
// from: - | yields: Address
MATCH (e1:Entity)-[:CONTROLS]->(:Address)-[f1:SENT]-(c:Address)-[f2:SENT]-(:Address)<-[:CONTROLS]-(e2:Entity)
WHERE e1.id < e2.id AND split(toLower(e1.name), ' ')[0] <> split(toLower(e2.name), ' ')[0] AND NOT (e1)-[:CONTROLS]->(c) AND NOT (e2)-[:CONTROLS]->(c)
RETURN c.key AS counterparty, e1.name AS first_entity, e2.name AS second_entity, collect(DISTINCT f1.asset) AS assets, count(*) AS links
ORDER BY links DESC LIMIT 25
