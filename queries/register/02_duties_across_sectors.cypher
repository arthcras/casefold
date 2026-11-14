// Sector register. Which duties are shared and which belong to one corner of the market: per duty in force on $on, the number of sectors and the categories it applies to, with its legal basis.
MATCH (d:SectorDuty)<-[:HAS_DUTY]-(s:Sector)-[:IN_CATEGORY]->(c:SectorCategory)
WHERE d.valid_from <= $on AND (d.valid_to IS NULL OR d.valid_to >= $on)
OPTIONAL MATCH (d)-[:DEFINED_IN]->(a:Article)
RETURN d.title AS duty, d.level AS level, d.kind AS kind, count(DISTINCT s) AS sectors, collect(DISTINCT c.name_nl) AS categories, collect(DISTINCT a.ref)[0] AS basis
ORDER BY sectors DESC, duty
