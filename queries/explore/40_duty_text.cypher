// What does the law say for this duty, per legal regime: the article in Dutch and in English, from when to when, and what replaces it?
// from: SectorDuty | yields: -
MATCH (d:SectorDuty {id:$id})-[:DEFINED_IN]->(a:Article)-[:PART_OF]->(l:Law)
OPTIONAL MATCH (a)-[:REPLACED_BY]->(n:Article)
RETURN d.title AS duty, l.short AS law, a.ref AS article, coalesce(a.valid_from, '') + ' – ' + coalesce(a.valid_to, '') AS valid,
       CASE WHEN (a.valid_from IS NULL OR a.valid_from <= $on) AND (a.valid_to IS NULL OR a.valid_to >= $on) THEN 'applies on ' + $on ELSE '' END AS today,
       n.ref AS replaced_by, a.text_local AS text_dutch, a.text_en AS text_english,
       CASE a.en_type WHEN 'summary' THEN 'summary, not the law text' ELSE a.en_type END AS english_version,
       CASE a.basis_kind WHEN 'summary' THEN 'summary' WHEN 'pending' THEN 'not read in yet' ELSE CASE WHEN a.verify THEN 'law text, to verify' ELSE 'law text, checked' END END AS text_status, a.read_in AS read_in, a.source_url AS source
ORDER BY coalesce(a.valid_from, '0000')
