// The sanctions lists a crypto screening checks against, who publishes them, and what the daily import found.
// from: - | yields: SanctionsList
MATCH (l:SanctionsList)
OPTIONAL MATCH (l)-[:PUBLISHED_BY]->(g:Regulator)
RETURN l.name AS list, g.short AS publisher, l.refresh AS refresh, l.imported AS imported, l.entries_total AS entries,
       l.addresses_total AS addresses, l.fetched AS fetched, l.url AS source
ORDER BY imported DESC, entries DESC, list
