// The same company, sanctioned by more than one authority or in more than one country: where else did it go wrong?
// from: - | yields: Entity
MATCH (e:Entity)<-[:AGAINST]-(k:Source {kind: 'case'})-[:IN_JURISDICTION]->(x:Jurisdiction)
OPTIONAL MATCH (k)-[:BY]->(g:Regulator)
WITH e, k, x, collect(g.short) AS by
ORDER BY k.date
WITH e, collect(x.code + ' ' + k.date + ' ' + k.measure + ' (' + reduce(s = '', a IN by | s + CASE s WHEN '' THEN '' ELSE ', ' END + a) + ')') AS cases, count(DISTINCT x) AS countries
WHERE size(cases) > 1
RETURN e.group AS group, e.name AS party, countries, cases
ORDER BY countries DESC, size(cases) DESC
