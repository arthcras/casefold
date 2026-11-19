// Every public crypto enforcement case: who, by whom, how much, which law, and the source. The Netherlands first, newest first.
// from: - | yields: Source
MATCH (k:Source {kind: 'case'})-[:IN_JURISDICTION]->(x:Jurisdiction)
OPTIONAL MATCH (k)-[:BY]->(g:Regulator)
OPTIONAL MATCH (k)-[r:VIOLATED]->(w:Law)
RETURN x.code AS country, k.date AS date, k.party AS party, collect(DISTINCT g.short) AS authorities, k.measure AS measure,
       k.amount AS amount, k.currency AS currency, k.amount_note AS amount_note, collect(DISTINCT w.short) AS laws, k.status AS status, k.url AS source, k.decision AS decision, k.verify AS verify, k.id AS id
ORDER BY CASE x.code WHEN 'NL' THEN 0 ELSE 1 END, date DESC
