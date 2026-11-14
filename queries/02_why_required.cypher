// Why is this document type required? Follow the chain Client -> Obligation <- Article -> Law, with the passage and the source.
// param: doctype (e.g. source_of_funds, person_id, proof_of_address)
MATCH (c:Client)-[:SUBJECT_TO]->(o:Obligation)-[:PROVEN_BY]->(t:DocumentType {key:$doctype})
MATCH (a:Article)-[i:IMPOSES]->(o)
OPTIONAL MATCH (a)-[:PART_OF]->(l:Law)
RETURN t.name AS document, o.text AS obligation, i.condition AS applies, a.ref AS article, l.title AS law, left(i.quote, 220) AS passage, a.source_url AS source, CASE WHEN a.verify THEN 'to verify' ELSE 'checked' END AS text_status
ORDER BY article;
