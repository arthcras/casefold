// Which authorities are there, and in how many sectors are they the AML supervisor or have another role?
// from: - | yields: Regulator
MATCH (g:Regulator)-[v:SUPERVISES]->(s:Sector)
RETURN 'Regulator' AS _type, g.id AS _id, g.short AS authority, g.name AS name, count(DISTINCT CASE WHEN v.aml THEN s END) AS sectors_as_aml_supervisor, count(DISTINCT CASE WHEN NOT v.aml THEN s END) AS sectors_other_role
ORDER BY sectors_as_aml_supervisor DESC, sectors_other_role DESC, authority
