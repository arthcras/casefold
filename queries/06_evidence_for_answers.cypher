// For every question in the client acceptance: the answer, its status and the documents (with the place in the document) it rests on
MATCH (c:Client)-[:HAS_QUESTION]->(q:Question)
OPTIONAL MATCH (d:Document)-[a:ANSWERS]->(q)
RETURN q.id AS id, q.text AS question, q.status AS status, q.answer AS answer, collect(d.id + ' ' + d.title + ' @ ' + a.where) AS evidence
ORDER BY id;
