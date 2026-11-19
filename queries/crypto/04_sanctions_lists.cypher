// The sanctions lists a crypto screening checks against, who publishes them and whether they are imported yet.
// from: - | yields: SanctionsList
MATCH (l:SanctionsList)
OPTIONAL MATCH (l)-[:PUBLISHED_BY]->(g:Regulator)
RETURN l.name AS list, g.short AS publisher, l.refresh AS refresh, l.imported AS imported, l.url AS source
ORDER BY list
