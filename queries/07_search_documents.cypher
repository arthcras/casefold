// Full-text search in the documents of the case. param: term (e.g. nominee, director, Panama)
MATCH (d:Document) SEARCH d IN (FULLTEXT INDEX doc_text FOR $term LIMIT 5) SCORE AS relevance
OPTIONAL MATCH (d)-[:MENTIONS]->(p:Party)
RETURN d.id AS doc, d.title AS title, relevance, collect(p.name) AS mentions
ORDER BY relevance DESC;
