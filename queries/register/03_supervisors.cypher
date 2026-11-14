// Sector register. Per supervisor: the sectors where it is the AML supervisor and where it has another role (prudential), the categories and sectors it supervises, and the office files in the register. "aan te wijzen": the AMLR sectors whose supervisor is still to be designated by AMvB (Iwt art. 1.3).
MATCH (g:Regulator)-[v:SUPERVISES]->(s:Sector)-[:IN_CATEGORY]->(c:SectorCategory)
OPTIONAL MATCH (o:OfficeFile)-[:IN_SECTOR]->(s)
RETURN g.short AS supervisor, count(DISTINCT CASE WHEN v.aml THEN s END) AS sectors_aml, count(DISTINCT CASE WHEN NOT v.aml THEN s END) AS sectors_other_role, collect(DISTINCT c.name_nl) AS categories, collect(DISTINCT s.local) AS sector_names, count(DISTINCT o) AS office_files
ORDER BY sectors_aml DESC
