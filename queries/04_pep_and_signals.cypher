// PEPs in the structure, how they are connected to the client, and the signals raised about them
MATCH (v:Person {pep:true})
MATCH p = (v)-[:OWNS|DIRECTOR_OF]->{1,3}(c:Client)
OPTIONAL MATCH (s:Signal)-[:ABOUT]->(v)
RETURN v.name AS pep, v.pep_role AS role, [n IN nodes(p) | n.name] AS path, [r IN relationships(p) | type(r) + ' ' + coalesce(toString(r.pct) + '%', '')] AS links, collect(DISTINCT s.title) AS signals;
