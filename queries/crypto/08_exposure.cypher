// Direct exposure on chain: the counterparties of a listed entity's addresses, what moved each way, and whether the
// counterparty is itself on a list. param: entity (e.g. OFAC:36025). Facts from the chain; who controls an unlisted address is not known.
// from: Entity | yields: Address
MATCH (e:Entity {id: $entity})-[:CONTROLS]->(a:Address)-[f:SENT]-(c:Address)
WHERE NOT (e)-[:CONTROLS]->(c)
WITH c, f, startNode(f) = a AS outgoing
OPTIONAL MATCH (x:Entity)-[:CONTROLS]->(c)
RETURN c.key AS counterparty, c.chain AS chain, f.asset AS asset,
       sum(CASE WHEN outgoing THEN f.amount ELSE 0.0 END) AS sent_to, sum(CASE WHEN outgoing THEN 0.0 ELSE f.amount END) AS received_from,
       sum(f.count) AS transfers, min(f.first) AS first, max(f.last) AS last, collect(DISTINCT x.name) AS listed_as
ORDER BY sent_to + received_from DESC
