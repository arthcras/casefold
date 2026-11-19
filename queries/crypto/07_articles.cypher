// Per article: the duty, how often it was violated in the cases (with the total of the fines in EUR, as published), and the article that replaced it.
// from: - | yields: Article
MATCH (x:Article)
OPTIONAL MATCH (k:Source {kind: 'case'})-[:VIOLATED_ARTICLE]->(x)
OPTIONAL MATCH (x)-[:REPLACED_BY]->(y:Article)
WITH x, y, collect(k) AS ks
RETURN x.law_short + ' art. ' + x.art AS article, x.heading AS heading, x.duty AS duty, x.status AS status, size(ks) AS cases,
       [k IN ks | k.party] AS parties,
       reduce(t = 0.0, k IN ks | t + CASE WHEN k.currency = 'EUR' AND k.measure ENDS WITH 'fine' THEN coalesce(k.amount, 0.0) ELSE 0.0 END) AS fines_eur,
       CASE WHEN y IS NULL THEN null ELSE y.law_short + ' art. ' + y.art END AS replaced_by
ORDER BY cases DESC, x.law_short, size(x.art), x.art
