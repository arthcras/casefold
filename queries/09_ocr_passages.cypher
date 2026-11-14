// Where in the scanned documents does a term appear, on which page and position, and how sure is the OCR? param: term (e.g. nominee, getekend, bevoegd)
MATCH (k:Chunk) SEARCH k IN (FULLTEXT INDEX chunk_text FOR $term LIMIT 8) SCORE AS relevance
MATCH (d:Document)-[:HAS_CHUNK]->(k)
RETURN d.id AS doc, d.file AS file, k.page AS page, k.bbox AS box_px, k.confidence AS ocr_conf, k.low_conf_words AS unsure_words, left(replace(k.text, '\n', ' | '), 140) AS text, relevance
ORDER BY relevance DESC;
