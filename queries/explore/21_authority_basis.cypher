// On what legal basis does this authority act, and where does that come from?
// from: Regulator | yields: -
MATCH (g:Regulator {id:$id})
RETURN g.short AS authority, g.name AS name, g.basis AS legal_basis, g.basis_url AS source, g.basis_source AS taken_from, CASE WHEN g.basis_verify THEN 'to verify' ELSE 'checked' END AS basis_status
