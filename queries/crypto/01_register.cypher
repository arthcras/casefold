// Who supervises crypto, in which role, under which laws? Per jurisdiction; wave 1 = the Netherlands.
// from: - | yields: Jurisdiction
MATCH (x:Jurisdiction)<-[:IN_JURISDICTION]-(s:Sector)<-[v:SUPERVISES]-(g:Regulator)
OPTIONAL MATCH (s)-[:SUBJECT_TO]->(w:Law)
RETURN x.wave AS wave, x.code AS code, x.name AS jurisdiction, x.regime AS regime,
       collect(DISTINCT g.short + ' (' + v.role + ')') AS supervisors, collect(DISTINCT w.short) AS laws, x.verify AS verify
ORDER BY wave, jurisdiction
