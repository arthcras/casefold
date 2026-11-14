// Which legislation applies to this sector?
// from: Sector | yields: Law
MATCH (s:Sector {id:$id})-[r:SUBJECT_TO]->(l:Law)
RETURN 'Law' AS _type, l.id AS _id, l.short AS law, l.title AS title, CASE WHEN l.valid_from IS NULL OR l.valid_from <= $on THEN 'in force' ELSE 'from ' + l.valid_from END AS status, r.source AS link_from
ORDER BY law
