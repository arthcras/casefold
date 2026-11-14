// Sector register. Sector-specific supervision depends on whether the service needs a licence: per sector the licence (or registration, notification, appointment, admission), who grants it, and whether that is the same body as the AML supervisor.
MATCH (s:Sector)-[:REQUIRES_LICENCE]->(x:Licence)
OPTIONAL MATCH (x)-[:GRANTED_BY]->(g:Regulator)
OPTIONAL MATCH (a:Regulator)-[:SUPERVISES {aml:true}]->(s)
OPTIONAL MATCH (s)-[:IN_CATEGORY]->(c:SectorCategory)
RETURN c.name_nl AS category, s.local AS sector, x.kind AS kind, x.name AS licence, x.basis AS basis, g.short AS granted_by, a.short AS aml_supervisor,
       CASE WHEN x.kind = 'none' THEN 'AML supervision only' WHEN g.id = a.id THEN 'one body: licence and AML' ELSE 'two bodies' END AS supervision, x.verify AS to_verify, c.order AS cat_order
ORDER BY cat_order, sector
