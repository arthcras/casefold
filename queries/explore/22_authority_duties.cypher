// Which duties answer to this authority (as AML supervisor of the sector, or directly, like FIU-Nederland or the AP)?
// from: Regulator | yields: SectorDuty
MATCH (g:Regulator {id:$id})-[v:SUPERVISES]->(s:Sector)-[:HAS_DUTY]->(d:SectorDuty)
WHERE (v.aml AND coalesce(d.authority, 'supervisor') = 'supervisor') OR d.authority = g.short
WITH * WHERE d.valid_from <= $on AND (d.valid_to IS NULL OR d.valid_to >= $on)
RETURN 'SectorDuty' AS _type, d.id AS _id, d.level AS level, d.title AS duty, count(DISTINCT s) AS sectors
ORDER BY sectors DESC, duty
