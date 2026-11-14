// Law file. Search the articles of this law for a word ($term, e.g. melding or suspicion), full text.
CALL db.index.fulltext.queryNodes('law_text', $term) YIELD node, score
RETURN node.number AS article, node.heading AS heading, round(score, 2) AS score, left(node.text, 200) AS text
ORDER BY score DESC LIMIT 15
