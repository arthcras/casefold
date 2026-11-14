// Besides the UBO: the KYC duties per client of the office's sector (towards the AML supervisor or FIU-Nederland), and what they mean for this client today ($on): triggered by which transaction (CDD threshold, FIU indicator), and the passage it rests on. The office's own duties are in the office file (office/01).
MATCH (c:Client)-[:CLIENT_OF]->(i:Institution)-[:IN_SECTOR]->(s:Sector)-[:HAS_DUTY]->(d:SectorDuty)
WHERE d.valid_from <= $on AND (d.valid_to IS NULL OR d.valid_to >= $on)
OPTIONAL MATCH (g:Regulator)-[:SUPERVISES {aml:true}]->(s)
OPTIONAL MATCH (c)-[:MADE]->(t:Transaction)
  WHERE d.amount IS NOT NULL AND t.amount >= d.amount AND (size(d.tx) = 0 OR t.kind IN d.tx) AND (d.payment IN [null, 'any'] OR t.payment = d.payment)
WITH c, i, s, d, g.short AS supervisor, collect(t.id + ' ' + t.kind + ' EUR ' + toString(t.amount) + ' ' + t.payment) AS hits
OPTIONAL MATCH (c)-[:COUNTERPARTY_OF|HAS_COUNTERPARTY]-(p:Counterparty)-[:SCREENING_HIT]->(h:ScreeningHit)
WITH c, i, s, d, supervisor, hits, collect(DISTINCT p.name + ' (' + toString(h.score) + '%)') AS sanction_hits,
     (coalesce(d.independent, false) OR NOT (s.only_duties IS NOT NULL AND (s.cdd = false OR $on > coalesce(s.cdd_until, '9999-12-31') OR $on < coalesce(s.cdd_from, '0000-01-01')) AND NOT d.id IN s.only_duties)) AS active
OPTIONAL MATCH (d)-[:DEFINED_IN]->(a:Article)-[:PART_OF]->(l:Law) WHERE (a.valid_from IS NULL OR a.valid_from <= $on) AND (a.valid_to IS NULL OR a.valid_to >= $on)
WITH c, i, s, d, supervisor, hits, sanction_hits, active, collect(a.ref) AS basis, any(x IN collect(a.verify) WHERE x) AS to_verify, collect(DISTINCT a.basis_kind) AS basis_kind
RETURN CASE coalesce(d.authority, 'supervisor') WHEN 'supervisor' THEN supervisor ELSE d.authority END AS authority, d.level AS level, d.title AS duty, d.kind AS kind,
  CASE
    WHEN NOT active THEN 'not applicable: ' + s.scope_note
    WHEN d.kind = 'obliged_from' THEN CASE WHEN $on < d.from_date THEN 'not yet: obliged from ' + d.from_date ELSE 'applies (obliged since ' + d.from_date + ')' END
    WHEN d.kind IN ['always', 'periodic', 'scope_limit'] THEN 'applies' + CASE WHEN d.frequency IS NULL THEN '' ELSE ' (' + d.frequency + ')' END
    WHEN d.kind = 'threshold' THEN CASE WHEN size(hits) > 0 THEN 'CDD required: ' + reduce(x = '', h IN hits | x + CASE WHEN x = '' THEN '' ELSE '; ' END + h) ELSE 'not triggered' END
    WHEN d.kind = 'indicator' THEN CASE WHEN size(hits) > 0 THEN 'REPORT to FIU-NL: ' + reduce(x = '', h IN hits | x + CASE WHEN x = '' THEN '' ELSE '; ' END + h) ELSE 'no objective indicator met' END
    WHEN d.kind = 'prohibition' THEN CASE WHEN size(hits) > 0 THEN 'VIOLATION: ' + reduce(x = '', h IN hits | x + CASE WHEN x = '' THEN '' ELSE '; ' END + h) ELSE 'complied with' END
    WHEN d.kind = 'scope' THEN CASE WHEN size(hits) > 0 THEN 'in scope: ' + reduce(x = '', h IN hits | x + CASE WHEN x = '' THEN '' ELSE '; ' END + h) ELSE 'out of scope (below the amount)' END
    WHEN d.kind = 'screening' THEN CASE WHEN size(sanction_hits) > 0 THEN 'REPORT hit to ' + supervisor + ': ' + reduce(x = '', h IN sanction_hits | x + CASE WHEN x = '' THEN '' ELSE '; ' END + h) ELSE 'no sanctions hit' END
    WHEN d.kind = 'risk_band' THEN CASE c.risk_band WHEN 'high' THEN 'EDD required: ' + reduce(x = '', f IN coalesce(c.risk_factors, []) | x + CASE WHEN x = '' THEN '' ELSE '; ' END + f)
         WHEN 'low' THEN 'simplified CDD possible: ' + reduce(x = '', f IN coalesce(c.risk_factors, []) | x + CASE WHEN x = '' THEN '' ELSE '; ' END + f) ELSE 'standard CDD' END
    WHEN d.kind = 'declaration' THEN CASE WHEN size(hits) > 0 THEN 'ASK for the customs declaration: ' + reduce(x = '', h IN hits | x + CASE WHEN x = '' THEN '' ELSE '; ' END + h) ELSE 'not triggered' END
    WHEN d.kind = 'freeze' THEN CASE WHEN size(sanction_hits) > 0 THEN 'FREEZE: ' + reduce(x = '', h IN sanction_hits | x + CASE WHEN x = '' THEN '' ELSE '; ' END + h) ELSE 'no sanctions hit' END
    WHEN d.kind = 'service_scope' THEN CASE WHEN c.service_in_scope THEN 'in scope: ' + coalesce(c.service, 'listed service') ELSE 'out of scope: ' + coalesce(c.service, '') END
  END AS status,
  basis, basis_kind, to_verify, d.id AS duty_id
ORDER BY CASE d.level WHEN 'client' THEN 0 ELSE 1 END, CASE WHEN status STARTS WITH 'VIOLATION' OR status STARTS WITH 'REPORT' OR status STARTS WITH 'FREEZE' THEN 0 WHEN status STARTS WITH 'CDD' OR status STARTS WITH 'in scope' THEN 1 ELSE 2 END, duty
