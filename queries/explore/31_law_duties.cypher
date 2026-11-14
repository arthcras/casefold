// Which duties rest on this law, and with which passage?
// from: Law | yields: SectorDuty
MATCH (l:Law {id:$id})<-[:PART_OF]-(a:Article)<-[:DEFINED_IN]-(d:SectorDuty)
OPTIONAL MATCH (s:Sector)-[:HAS_DUTY]->(d)
WITH * WHERE d.valid_from <= $on AND (d.valid_to IS NULL OR d.valid_to >= $on)
RETURN 'SectorDuty' AS _type, d.id AS _id, a.ref AS article, d.title AS duty, count(DISTINCT s) AS sectors, CASE WHEN a.verify THEN 'to verify' ELSE 'checked' END AS text_status
ORDER BY sectors DESC, duty
