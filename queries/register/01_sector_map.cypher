// Sector register. The entry: jurisdiction, then sector, then its supervisor(s) on $on. Per sector: the supervisors with their role (the AML supervisor marked), the category and FATF scope, whether it is obliged today or from which date, and how many duties it has.
MATCH (j:Jurisdiction)<-[:IN_JURISDICTION]-(s:Sector)-[:IN_CATEGORY]->(c:SectorCategory), (s)-[:IN_SCOPE]->(f:FatfScope)
OPTIONAL MATCH (g:Regulator)-[v:SUPERVISES]->(s)
WITH j, s, c, f, collect(DISTINCT g.short + CASE WHEN v.aml THEN ' (AML)' ELSE ' (' + coalesce(v.role, '') + ')' END) AS supervisors
OPTIONAL MATCH (s)-[:HAS_DUTY]->(d:SectorDuty) WHERE d.valid_from <= $on AND (d.valid_to IS NULL OR d.valid_to >= $on)
RETURN j.name AS jurisdiction, s.local AS sector, supervisors, s.expected_supervisor AS expected_supervisor, c.name_nl AS category, f.id AS fatf,
       CASE WHEN s.obliged_from IS NULL THEN 'obliged' WHEN s.obliged_from <= $on THEN 'obliged since ' + s.obliged_from ELSE 'from ' + s.obliged_from END AS status,
       count(DISTINCT d) AS duties, c.order AS cat_order
ORDER BY jurisdiction, cat_order, sector
