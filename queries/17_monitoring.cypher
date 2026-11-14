// Ongoing monitoring on $on: the client's transactions with its sub-clients (KYCC), against the expected profile of the service it uses. Per rule: volume above the profile, cash outside the profile, possible structuring just below a cash limit, high-risk countries (also one level further: the sub-clients of a sub-client), sanctions hits, sub-clients with open KYCC, each with the passage it rests on. Without customer due diligence in the sector, only the cash ban is watched (structuring).
MATCH (c:Client)-[:USES]->(v:Service), (c)-[:CLIENT_OF]->(:Institution)-[:IN_SECTOR]->(s:Sector)
WITH c, v, s,
     coalesce(s.cdd, true) AND (s.cdd_until IS NULL OR s.cdd_until >= $on) AND (s.cdd_from IS NULL OR s.cdd_from <= $on) AS cdd,
     EXISTS { (s)-[:HAS_DUTY]->(b:SectorDuty {id:'NL:duty:cash-ban'}) WHERE b.valid_from <= $on AND (b.valid_to IS NULL OR b.valid_to >= $on) } AS cash_ban
MATCH (m:MonitoringRule)
OPTIONAL MATCH (c)-[:MADE]->(t:Transaction {series:'monitoring'}) WHERE t.date <= $on
WITH c, v, cdd, cash_ban, m, CASE WHEN cash_ban THEN 3000 ELSE 10000 END AS lim,
     sum(t.amount) AS total, count(DISTINCT substring(t.date, 0, 7)) AS months,
     collect(t) AS txs
WITH c, v, cdd, cash_ban, m, lim, total, months, txs,
     [t IN txs WHERE t.payment = 'cash'] AS cash,
     [t IN txs WHERE t.payment = 'cash' AND t.amount >= m.band * lim AND t.amount < lim] AS near
WITH c, v, cdd, cash_ban, m, lim, total, months, txs, cash, near,
     [a IN near WHERE any(b IN near WHERE b.id <> a.id AND abs(a.day - b.day) <= m.window_days)] AS pieces
OPTIONAL MATCH (c)-[:MADE]->(t2:Transaction {series:'monitoring'})-[:WITH]->(k:Counterparty)-[:LOCATED_IN]->(g:Country) WHERE t2.date <= $on
WITH c, v, cdd, cash_ban, m, lim, total, months, cash, pieces,
     collect(DISTINCT CASE WHEN m.check = 'high_risk_country' AND g.code IN m.countries THEN k.name + ' (' + g.code + ')' END) AS hr,
     collect(DISTINCT CASE WHEN m.check = 'sanctions_hit' AND EXISTS { (k)-[:SCREENING_HIT]->() } THEN k.name END) AS sh,
     collect(DISTINCT CASE WHEN m.check = 'kycc_open' AND k.checks_done < k.checks_total THEN k.name + ' (' + toString(k.checks_done) + '/' + toString(k.checks_total) + ')' END) AS ko
OPTIONAL MATCH (c)-[:MADE]->(t3:Transaction {series:'monitoring'})-[:WITH]->(:Counterparty)<-[:COUNTERPARTY_OF]-(k2:Counterparty)-[:LOCATED_IN]->(g2:Country)
  WHERE t3.date <= $on AND m.check = 'indirect_high_risk' AND g2.code IN m.countries
WITH c, v, m, cdd, cash_ban, lim, total, months, cash, pieces, hr, sh, ko, collect(DISTINCT k2.name + ' (' + g2.code + ', via a sub-client)') AS ih,
     (cdd OR (m.check = 'structuring' AND cash_ban)) AS active
OPTIONAL MATCH (m)-[:DEFINED_IN]->(a:Article)
WITH c, v, m, active, lim, total, months, cash, pieces, hr, sh, ko, ih, collect(a.ref) AS basis, any(x IN collect(a.verify) WHERE x) AS to_verify
WITH v, m, active, basis, to_verify,
  CASE m.check
    WHEN 'volume_above_profile' THEN CASE WHEN months > 0 AND total / months > m.factor * v.expected_monthly
         THEN 'FLAG: EUR ' + toString(toInteger(total / months)) + ' a month against EUR ' + toString(v.expected_monthly) + ' expected' END
    WHEN 'cash_outside_profile' THEN CASE WHEN size(cash) > 0 AND NOT v.cash_allowed THEN 'FLAG: ' + toString(size(cash)) + ' cash payment(s), the service expects none' END
    WHEN 'structuring' THEN CASE WHEN size(pieces) > 0 THEN 'FLAG: ' + reduce(x = '', t IN pieces | x + CASE WHEN x = '' THEN '' ELSE ', ' END + t.id + ' ' + t.date + ' EUR ' + toString(t.amount)) + ' (limit EUR ' + toString(lim) + ')' END
    WHEN 'high_risk_country' THEN CASE WHEN size(hr) > 0 THEN 'FLAG: ' + reduce(x = '', n IN hr | x + CASE WHEN x = '' THEN '' ELSE '; ' END + n) END
    WHEN 'sanctions_hit' THEN CASE WHEN size(sh) > 0 THEN 'FLAG: ' + reduce(x = '', n IN sh | x + CASE WHEN x = '' THEN '' ELSE '; ' END + n) END
    WHEN 'indirect_high_risk' THEN CASE WHEN size(ih) > 0 THEN 'FLAG: ' + reduce(x = '', n IN ih | x + CASE WHEN x = '' THEN '' ELSE '; ' END + n) END
    WHEN 'kycc_open' THEN CASE WHEN size(ko) > 0 THEN 'FLAG: ' + reduce(x = '', n IN ko | x + CASE WHEN x = '' THEN '' ELSE '; ' END + n) END
  END AS flag
RETURN v.name AS service, m.title AS rule, m.check AS check,
       CASE WHEN NOT active THEN 'not applicable (no customer due diligence in this sector on this date)' ELSE coalesce(flag, 'ok') END AS status,
       basis, to_verify, m.id AS rule_id
ORDER BY CASE WHEN status STARTS WITH 'FLAG' THEN 0 ELSE 1 END, rule
