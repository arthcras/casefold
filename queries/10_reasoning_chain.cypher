// How did we reach each conclusion? The answers of the latest session as reasoning chains (observation -> rule -> derived -> conclusion -> decision), with what each step cites
MATCH (s:Session) WITH s ORDER BY s.started DESC LIMIT 1
MATCH (s)-[:ASKED]->(q:Ask)-[:ANSWERED_BY]->(a:Answer)-[:HAS_STEP]->(step:Step)
OPTIONAL MATCH (step)-[:CITES]->(e)
RETURN q.text AS question, step.ord AS n, step.kind AS kind, step.text AS reasoning, step.confidence AS confidence,
       collect(DISTINCT coalesce(e.title, e.name, e.ref, e.id)) AS cites
ORDER BY question, n;
