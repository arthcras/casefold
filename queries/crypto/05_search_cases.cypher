// Search the cases in full text (title, summary, what happened on chain, party). param: q (e.g. sanctions, registratie, ransomware)
// from: - | yields: Source
MATCH (k:Source {kind: 'case'}) SEARCH k IN (FULLTEXT INDEX crypto_case_text FOR $q LIMIT 10) SCORE AS relevance
RETURN k.party AS party, k.date AS date, k.title AS title, k.url AS source, relevance
ORDER BY relevance DESC
