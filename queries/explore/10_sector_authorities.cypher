// Who supervises this sector, in which role, and on what legal basis?
// from: Sector | yields: Regulator
MATCH (g:Regulator)-[v:SUPERVISES]->(s:Sector {id:$id})
RETURN 'Regulator' AS _type, g.id AS _id, g.short AS authority, CASE WHEN v.aml THEN 'AML supervisor' ELSE replace(coalesce(v.role, ''), '_', ' ') END AS role, g.basis AS legal_basis, CASE WHEN g.basis_verify THEN 'to verify' ELSE 'checked' END AS basis_status
ORDER BY CASE WHEN v.aml THEN 0 ELSE 1 END, authority
