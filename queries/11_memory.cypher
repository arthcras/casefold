// What does this case remember? Short-term sessions, medium-term episodes (decisions and open items) and long-term patterns (proposed or approved)
MATCH (k:Case)
OPTIONAL MATCH (k)-[:HAS_SESSION]->(s:Session)
OPTIONAL MATCH (k)-[:HAS_EPISODE]->(e:Episode)
OPTIONAL MATCH (k)-[:PROPOSED]->(p:Pattern)
RETURN 'short-term' AS memory, s.id AS id, 'until ' + s.expires AS detail, null AS items
UNION
MATCH (k:Case)-[:HAS_EPISODE]->(e:Episode)
RETURN 'medium-term' AS memory, e.id AS id, 'decision: ' + e.decision AS detail, e.open_items AS items
UNION
MATCH (k:Case)-[:PROPOSED]->(p:Pattern)
RETURN 'long-term' AS memory, p.id AS id, p.status + ': ' + p.title AS detail, [p.action] AS items;
