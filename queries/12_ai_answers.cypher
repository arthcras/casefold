// What did the AI answer, and on what basis? Per claim: grounded or not, the evidence it cites, and the query (tool call) in which the AI read that evidence
MATCH (s:Session {by:'ai'})-[:ASKED]->(q:Ask)-[:ANSWERED_BY]->(a:Answer)-[:HAS_CLAIM]->(c:Claim)
OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(e)
OPTIONAL MATCH (q)-[:USED]->(t:ToolCall)-[:READ]->(e)
WITH q, a, c, e, collect(DISTINCT t.ord) AS calls
RETURN q.text AS question, a.id AS answer, CASE WHEN EXISTS { (:Answer)-[:REVISES]->(a) } THEN 'revised' ELSE 'current' END AS version,
       c.ord AS claim, c.text AS statement, c.status AS status,
       collect(DISTINCT labels(e)[0] + ': ' + coalesce(e.title, e.name, e.ref, e.id) + CASE WHEN size(calls) > 0 THEN ' (read in query ' + toString(calls[0]) + ')' ELSE '' END) AS evidence
ORDER BY answer, claim;
