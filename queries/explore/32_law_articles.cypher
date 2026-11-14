// Which articles of this law are in the register, in Dutch and in English?
// from: Law | yields: SectorDuty
MATCH (a:Article)-[:PART_OF]->(l:Law {id:$id}) OPTIONAL MATCH (d:SectorDuty)-[:DEFINED_IN]->(a)
RETURN 'SectorDuty' AS _type, d.id AS _id, a.ref AS article, d.title AS duty, a.text_local AS text_dutch, a.text_en AS text_english,
       CASE WHEN a.basis_kind = 'summary' THEN 'summary' WHEN a.verify THEN 'law text, to verify' ELSE 'law text, checked' END AS text_status
ORDER BY article
