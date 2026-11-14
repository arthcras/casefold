// Full-text search in the law articles copied into the case. param: term (e.g. "source of wealth", address)
MATCH (a:Article) SEARCH a IN (FULLTEXT INDEX article_text FOR $term LIMIT 5) SCORE AS relevance
OPTIONAL MATCH (a)-[i:IMPOSES]->(o:Obligation)
RETURN a.ref AS article, relevance, collect(DISTINCT o.text) AS obligations, left(a.text_en, 200) AS text, a.source_url AS source
ORDER BY relevance DESC;
