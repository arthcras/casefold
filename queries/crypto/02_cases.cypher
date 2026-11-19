// Every public crypto enforcement case: who, by whom, how much, which law, and the source. The Netherlands first, newest first.
// from: - | yields: Source
MATCH (k:Source {kind: 'case'})-[:IN_JURISDICTION]->(x:Jurisdiction)
OPTIONAL MATCH (k)-[:BY]->(g:Regulator)
OPTIONAL MATCH (k)-[:TYPOLOGY]->(ty:RiskCategory)
OPTIONAL MATCH (k)-[r:VIOLATED]->(w:Law)
RETURN x.code AS country, k.date AS date, k.party AS party, collect(DISTINCT g.short) AS authorities, k.measure AS measure,
       k.amount AS amount, k.currency AS currency, k.amount_note AS amount_note, collect(DISTINCT w.short + CASE WHEN r.art IS NULL OR r.art = '' THEN '' ELSE ' art. ' + r.art + CASE WHEN size(coalesce(r.lids, [])) > 0 THEN '(' + reduce(t = '', l IN r.lids | t + CASE t WHEN '' THEN '' ELSE ')(' END + l) + ')' ELSE '' END END) AS laws, collect(DISTINCT ty.name) AS typologies, k.status AS status, k.url AS source, k.decision AS decision, k.verify AS verify, k.id AS id
ORDER BY CASE x.code WHEN 'NL' THEN 0 ELSE 1 END, date DESC
