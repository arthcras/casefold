// Which other sectors are in the same category, and who is their AML supervisor?
// from: Sector | yields: Sector
MATCH (s:Sector {id:$id})-[:IN_CATEGORY]->(c:SectorCategory)<-[:IN_CATEGORY]-(o:Sector) WHERE o <> s
OPTIONAL MATCH (g:Regulator)-[:SUPERVISES {aml:true}]->(o)
RETURN 'Sector' AS _type, o.id AS _id, c.name_nl AS category, o.local AS sector, g.short AS aml_supervisor
ORDER BY sector
