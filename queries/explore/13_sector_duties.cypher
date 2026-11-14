// Which duties does the office itself have in this sector on $on (organisation: risk assessment, training, sanctions procedure)?
// from: Sector | yields: SectorDuty
MATCH (s:Sector {id:$id})-[:HAS_DUTY]->(d:SectorDuty {level:'office'}) WHERE d.valid_from <= $on AND (d.valid_to IS NULL OR d.valid_to >= $on)
OPTIONAL MATCH (d)-[:DEFINED_IN]->(a:Article) WHERE (a.valid_from IS NULL OR a.valid_from <= $on) AND (a.valid_to IS NULL OR a.valid_to >= $on)
RETURN 'SectorDuty' AS _type, d.id AS _id, d.level AS level, d.title AS duty, coalesce(d.authority, 'supervisor') AS towards, collect(a.ref)[0] AS basis
ORDER BY level DESC, duty
