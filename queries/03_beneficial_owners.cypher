// Who are the beneficial owners, asked from the office that serves the client (rule valid on $on, default today), ground by ground for the client's legal form (Uitvoeringsbesluit Wwft 2018 art. 3): shares and economic ownership, votes (for a foundation, association or cooperative: on amending the statutes; for a partnership: on amending the agreement), control via other means, trust roles, and the listed-issuer exception. Compared with the UBO declaration.
MATCH (c:Client)-[:CLIENT_OF]->(inst:Institution)-[:FOLLOWS]->(u:UboRule), (inst)-[:IN_SECTOR]->(sec:Sector)
WHERE coalesce(sec.cdd, true) AND (sec.cdd_until IS NULL OR sec.cdd_until >= $on) AND (sec.cdd_from IS NULL OR sec.cdd_from <= $on) AND u.valid_from <= $on AND (u.valid_to IS NULL OR u.valid_to >= $on)
MATCH (c)-[:HAS_LEGAL_FORM]->(f:LegalForm)
WITH c, u, CASE f.entity_type WHEN 'branch' THEN 'corporate' ELSE f.entity_type END AS et
MATCH (u)-[:HAS_GROUND]->(g:UboGround) WHERE g.entity_type = et
WITH c, u, et, collect(g) AS grounds,
     (et = 'corporate' AND (coalesce(c.listed, false) OR EXISTS { (l:Party {listed:true})-[:OWNS {pct:100}]->(c) })) AS exempt
MATCH (o:Party) WHERE (o:Person OR o:Group) AND (EXISTS { (o)-[:OWNS|BOARD_OF|MEMBER_OF|CONTROLS|ROLE_IN]->{1,5}(c) } OR EXISTS { (o)-[:CONTROLS]->(x) WHERE EXISTS { (x)-[:OWNS]->{1,4}(c) } })
OPTIONAL MATCH p = (o)-[:OWNS]->{1,5}(c)
WITH c, u, et, grounds, exempt, o,
     sum(reduce(x = 1.0, r IN relationships(p) | x * r.pct / 100.0)) AS em,
     sum(reduce(x = 1.0, r IN relationships(p)[0..-1] | x * CASE WHEN r.votes > 50 THEN 1.0 ELSE r.pct / 100.0 END) * last(relationships(p)).pct / 100.0) AS ec
OPTIONAL MATCH q = (o)-[:OWNS|BOARD_OF|MEMBER_OF]->{1,5}(c)
WITH c, u, et, grounds, exempt, o, em, ec,
     sum(reduce(x = 1.0, r IN relationships(q) | x * r.votes / 100.0)) AS vm,
     sum(reduce(x = 1.0, r IN relationships(q)[0..-1] | x * CASE WHEN r.votes > 50 THEN 1.0 ELSE r.votes / 100.0 END) * last(relationships(q)).votes / 100.0) AS vc
OPTIONAL MATCH (o)-[ri:ROLE_IN]->(c)
WITH c, u, et, grounds, exempt, o, collect(ri.role) AS roles,
     round(100 * CASE WHEN u.method = 'both' AND ec > em THEN ec ELSE em END, 1) AS ownership,
     round(100 * CASE WHEN u.method = 'both' AND vc > vm THEN vc ELSE vm END, 1) AS votes,
     EXISTS { (o)-[:CONTROLS]->(x) WHERE x = c OR EXISTS { (x)-[:OWNS]->{1,4}(c) } } AS control
WITH c, u, et, exempt, o, roles, ownership, votes, control,
     [g IN grounds WHERE NOT exempt AND (
          (g.ground = 'ownership_interest' AND ((g.op = '>' AND ownership > g.threshold) OR (g.op = '>=' AND ownership >= g.threshold)))
       OR (g.ground IN ['voting_rights', 'statute_votes', 'agreement_votes'] AND ((g.op = '>' AND votes > g.threshold) OR (g.op = '>=' AND votes >= g.threshold)))
       OR (g.ground = 'control_other_means' AND control)
       OR (g.ground IN roles AND (g.ground <> 'fgr_group' OR (coalesce(c.participants, 0) >= 150 AND c.licensed_manager)))) | g.name] AS grounds_met
OPTIONAL MATCH (d:Document)-[:OF_TYPE]->(t:DocumentType) WHERE t.key IN ['ubo_declaration', 'ubo_register_extract']
WITH u, et, exempt, o, roles, ownership, votes, control, grounds_met, collect(d) AS decls
RETURN u.name AS rule, et AS tested_as, o.name AS person, ownership, votes, control AS control_other_means, roles, grounds_met, size(grounds_met) > 0 AS ubo,
       CASE WHEN exempt THEN 'listed issuer or 100% subsidiary: excepted' ELSE '' END AS exception, coalesce(o.pep, false) AS pep,
       CASE WHEN size(decls) = 0 THEN 'no declaration in file' WHEN any(d IN decls WHERE d.text CONTAINS split(o.name, ' ')[1]) THEN 'declared' ELSE 'not declared' END AS declaration
ORDER BY ubo DESC, ownership DESC, votes DESC, person;
