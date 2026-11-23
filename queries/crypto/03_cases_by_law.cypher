// Where did the same law go wrong before? Per law: the cases that violated it, and the total published amount per currency.
// from: - | yields: Law
MATCH (k:Source {kind: 'case'})-[:VIOLATED]->(w:Law)
WITH w, collect(DISTINCT k) AS ks
RETURN w.short AS law, w.title AS title, size(ks) AS cases, [k IN ks | k.party] AS parties,
       reduce(t = 0.0, k IN ks | t + CASE WHEN k.currency = 'USD' THEN coalesce(k.amount, 0.0) ELSE 0.0 END) AS usd,
       reduce(t = 0.0, k IN ks | t + CASE WHEN k.currency = 'EUR' THEN coalesce(k.amount, 0.0) ELSE 0.0 END) AS eur
ORDER BY cases DESC, law
