// Which sectors are there, per category, and are they obliged today?
// from: - | yields: Sector
MATCH (s:Sector)-[:IN_CATEGORY]->(c:SectorCategory)
RETURN 'Sector' AS _type, s.id AS _id, c.name_nl AS category, s.local AS sector,
       CASE WHEN s.status = 'no_aml' THEN 'supervised, not an obliged entity' WHEN s.obliged_from IS NULL THEN 'obliged (Wwft)' ELSE 'obliged from ' + s.obliged_from END AS status, c.order AS cat_order
ORDER BY cat_order, sector
