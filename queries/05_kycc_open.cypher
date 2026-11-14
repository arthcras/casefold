// Know your customer's customer: which counterparties still need KYCC, ordered by volume, with country risk and screening hits
MATCH (k:Counterparty)-[r:COUNTERPARTY_OF]->(c:Client)
OPTIONAL MATCH (k)-[:LOCATED_IN]->(g:Country)
OPTIONAL MATCH (k)-[:SCREENING_HIT]->(h:ScreeningHit)
WITH k, r, g, h WHERE k.kycc_level <> 'none'
RETURN k.name AS counterparty, k.role AS role, g.code AS country, g.high_risk OR g.offshore AS risky_country, k.kycc_level AS kycc,
       toString(k.checks_done) + '/' + toString(k.checks_total) AS checks, k.kycc_complete AS complete, r.volume AS volume,
       CASE WHEN h IS NULL THEN null ELSE h.matched + ' (' + toString(h.score) + '%)' END AS screening_hit
ORDER BY complete, volume DESC;
