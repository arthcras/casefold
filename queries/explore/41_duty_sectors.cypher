// Which sectors have this duty?
// from: SectorDuty | yields: Sector
MATCH (d:SectorDuty {id:$id})<-[:HAS_DUTY]-(s:Sector)-[:IN_CATEGORY]->(c:SectorCategory)
WITH * WHERE d.valid_from <= $on AND (d.valid_to IS NULL OR d.valid_to >= $on)
RETURN 'Sector' AS _type, s.id AS _id, c.name_nl AS category, s.local AS sector, c.order AS cat_order
ORDER BY cat_order, sector
