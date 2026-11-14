// Which legislation is there, and to how many sectors does it apply?
// from: - | yields: Law
MATCH (l:Law)<-[:SUBJECT_TO]-(s:Sector)
RETURN 'Law' AS _type, l.id AS _id, l.short AS law, l.title AS title, CASE WHEN l.valid_from IS NULL OR l.valid_from <= $on THEN 'in force' ELSE 'from ' + l.valid_from END AS status, count(DISTINCT s) AS sectors
ORDER BY sectors DESC, law
