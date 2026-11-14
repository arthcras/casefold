// Which sectors does this authority supervise, and in which role?
// from: Regulator | yields: Sector
MATCH (g:Regulator {id:$id})-[v:SUPERVISES]->(s:Sector)-[:IN_CATEGORY]->(c:SectorCategory)
RETURN 'Sector' AS _type, s.id AS _id, c.name_nl AS category, s.local AS sector, CASE WHEN v.aml THEN 'AML supervisor' ELSE replace(coalesce(v.role, ''), '_', ' ') END AS role, c.order AS cat_order
ORDER BY cat_order, sector
