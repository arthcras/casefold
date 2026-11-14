// Law file. One article ($article, e.g. 16 or 3), paragraph by paragraph, with its points: the verbatim text as read in.
MATCH (a:LawArticle {number:$article})
OPTIONAL MATCH (a)-[:HAS_PARAGRAPH]->(p:LawParagraph)
OPTIONAL MATCH (p)-[:HAS_POINT]->(q:LawPoint)
WITH a, p, collect(q.label + '. ' + q.text) AS points
RETURN a.number AS article, a.heading AS heading, p.number AS paragraph, coalesce(p.text, a.text) AS text, points, p.seq AS seq
ORDER BY seq
