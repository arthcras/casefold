// Law file. Every article of this law with its heading and the number of paragraphs and points, in the order of the law.
MATCH (v:LawVersion)-[:HAS_ARTICLE]->(a:LawArticle)
OPTIONAL MATCH (a)-[:HAS_PARAGRAPH]->(p:LawParagraph)
OPTIONAL MATCH (p)-[:HAS_POINT]->(q:LawPoint)
RETURN a.number AS article, a.heading AS heading, count(DISTINCT p) AS paragraphs, count(DISTINCT q) AS points, left(a.text, 160) AS text, a.seq AS seq
ORDER BY seq
