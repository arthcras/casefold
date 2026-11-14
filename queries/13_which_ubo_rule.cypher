// Which UBO rule applies to this client, and why? The office that renders the service, the country, the supervisor, the rule it follows (today and later) and where the rule is written.
MATCH (c:Client)-[:CLIENT_OF]->(i:Institution)-[:IN_JURISDICTION]->(j:Jurisdiction)
OPTIONAL MATCH (i)-[:IN_SECTOR]->(s:Sector)<-[:SUPERVISES {aml:true}]-(g:Regulator)
OPTIONAL MATCH (i)-[f:FOLLOWS]->(u:UboRule)
OPTIONAL MATCH (u)-[:DEFINED_IN]->(a:Article)
RETURN c.name AS client, i.name AS office, j.name AS service_rendered_in, s.name AS sector, g.short AS supervisor, u.name AS ubo_rule, u.method AS method, u.fallback AS fallback,
       CASE WHEN u.valid_from = '2000-01-01' THEN 'in force' ELSE u.valid_from END AS valid_from, u.valid_to AS valid_to, collect(a.ref + CASE WHEN a.primary = false THEN ' (secondary source)' ELSE '' END) AS written_in, collect(coalesce(nullif(a.text_local, ''), a.text_en))[0] AS passage, u.source AS source, CASE WHEN u.verify THEN 'to verify' ELSE 'checked' END AS status
ORDER BY valid_to IS NULL, valid_to;
