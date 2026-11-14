// Which sectors are subject to this law?
// from: Law | yields: Sector
MATCH (l:Law {id:$id})<-[r:SUBJECT_TO]-(s:Sector)-[:IN_CATEGORY]->(c:SectorCategory)
OPTIONAL MATCH (g:Regulator)-[:SUPERVISES {aml:true}]->(s)
RETURN 'Sector' AS _type, s.id AS _id, c.name_nl AS category, s.local AS sector, g.short AS aml_supervisor, r.source AS link_from, c.order AS cat_order
ORDER BY cat_order, sector
