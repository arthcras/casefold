// Does this sector need a licence, which one, and who grants it?
// from: Sector | yields: Regulator
MATCH (s:Sector {id:$id})-[:REQUIRES_LICENCE]->(x:Licence)
OPTIONAL MATCH (x)-[:GRANTED_BY]->(g:Regulator)
RETURN 'Regulator' AS _type, g.id AS _id, x.kind AS kind, x.name AS licence, x.basis AS basis, g.short AS granted_by, CASE WHEN x.verify THEN 'to verify' ELSE 'checked' END AS basis_status
