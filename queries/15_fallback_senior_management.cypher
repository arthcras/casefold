// Fallback (Uitvoeringsbesluit Wwft 2018 art. 3 lid 1 onder a/c/d 2° jo. lid 6): the senior managing officials who are designated when nobody qualifies on the grounds: every director, or for a partnership every partner except a partner by way of a loan
MATCH (c:Client)-[:HAS_LEGAL_FORM]->(f:LegalForm), (c)-[:CLIENT_OF]->(:Institution)-[:IN_SECTOR]->(sec:Sector)
WHERE coalesce(sec.cdd, true) AND (sec.cdd_until IS NULL OR sec.cdd_until >= $on) AND (sec.cdd_from IS NULL OR sec.cdd_from <= $on)
  AND EXISTS { (c)-[:CLIENT_OF]->(:Institution)-[:FOLLOWS]->(u:UboRule) WHERE u.valid_from <= $on AND (u.valid_to IS NULL OR u.valid_to >= $on) }
WITH c, CASE f.entity_type WHEN 'branch' THEN 'corporate' ELSE f.entity_type END AS et
OPTIONAL MATCH (d:Person)-[:DIRECTOR_OF]->(c) WHERE et IN ['corporate', 'other_legal_entity']
OPTIONAL MATCH (v:Person)-[r:OWNS]->(c) WHERE et = 'partnership' AND NOT coalesce(r.lender, false)
WITH et, collect(DISTINCT d.name) + collect(DISTINCT v.name) AS names
UNWIND names AS name
RETURN DISTINCT et AS tested_as, name AS senior_managing_official
ORDER BY senior_managing_official;
