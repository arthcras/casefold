// Office file. The office itself on $on: for each periodic duty of its sector (risk assessment, training, sanctions procedure, SIRA, the annual return to the supervisor), the latest evidence on file, and whether it is up to date (within a year), overdue or missing.
MATCH (i:Institution)-[:IN_SECTOR]->(s:Sector)-[:HAS_DUTY]->(d:SectorDuty {kind:'periodic'})
WHERE d.valid_from <= $on AND (d.valid_to IS NULL OR d.valid_to >= $on)
  AND (coalesce(d.independent, false) OR NOT (s.only_duties IS NOT NULL AND (s.cdd = false OR $on > coalesce(s.cdd_until, '9999-12-31') OR $on < coalesce(s.cdd_from, '0000-01-01')) AND NOT d.id IN s.only_duties))
OPTIONAL MATCH (g:Regulator)-[:SUPERVISES {aml:true}]->(s)
OPTIONAL MATCH (i)-[:HAS_RECORD]->(r:OfficeRecord)-[:FULFILS]->(d) WHERE r.date <= $on
WITH i, g, d, max(r.date) AS last, toString(toInteger(substring($on, 0, 4)) - 1) + substring($on, 4) AS year_ago
OPTIONAL MATCH (d)-[:DEFINED_IN]->(a:Article)
RETURN i.name AS office, CASE coalesce(d.authority, 'supervisor') WHEN 'supervisor' THEN g.short ELSE d.authority END AS authority, d.title AS duty, d.frequency AS frequency, last AS latest_evidence,
       CASE WHEN last IS NULL THEN 'MISSING' WHEN last >= year_ago THEN 'up to date' ELSE 'OVERDUE' END AS status,
       collect(a.ref) AS basis, d.id AS duty_id
ORDER BY CASE status WHEN 'MISSING' THEN 0 WHEN 'OVERDUE' THEN 1 ELSE 2 END, duty
