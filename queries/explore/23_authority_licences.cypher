// Which licences does this authority grant, and for which sectors?
// from: Regulator | yields: Sector
MATCH (s:Sector)-[:REQUIRES_LICENCE]->(x:Licence)-[:GRANTED_BY]->(g:Regulator {id:$id})
RETURN 'Sector' AS _type, s.id AS _id, s.local AS sector, x.kind AS kind, x.name AS licence, x.basis AS basis
ORDER BY sector
