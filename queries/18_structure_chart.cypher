// What does the client's structure chart say, and what has the compliance officer confirmed? Every box and line of the chart as a proposal,
// with the place in the chart (page, position) and the text as drawn; confirmed proposals became the client's parties and OWNS / CONTROLS / BOARD_OF relations.
MATCH (p:Proposal)-[:STATED_IN]->(k:Chunk)<-[:HAS_CHUNK]-(d:Document)
OPTIONAL MATCH (p)-[:CREATED]->(n)
RETURN p.id AS proposal, p.status AS status, p.kind AS fact,
       CASE p.kind WHEN 'party' THEN p.from_name + ' (' + p.party_kind + coalesce(', ' + p.country, '') + ')'
                   ELSE p.from_name + ' → ' + p.to_name END AS what,
       CASE p.kind WHEN 'OWNS' THEN toString(p.pct) + '% shares, ' + toString(p.votes) + '% votes'
                   WHEN 'BOARD_OF' THEN toString(p.votes) + '% votes' WHEN 'CONTROLS' THEN p.basis ELSE '' END AS detail,
       d.title AS document, k.page AS page, k.bbox AS position, p.confirmed_by AS confirmed_by
ORDER BY toInteger(split(p.id, '-')[1]);
