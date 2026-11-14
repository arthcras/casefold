// The slice of the central rulebook that one case needs: the jurisdiction's laws, articles, the obligations they impose and the
// document types that prove them, plus the client's legal form and its document rules.  params: cc (e.g. CW), lf (e.g. CW:lf:nv)
MATCH (j:Jurisdiction {code:$cc})<-[r1:OF]-(l:Law)<-[r2:PART_OF]-(a:Article)-[r3:IMPOSES]->(o:Obligation)-[r4:PROVEN_BY]->(t:DocumentType)
RETURN j, r1, l, r2, a, r3, o, r4, t;
MATCH (f:LegalForm {id:$lf})-[r:REQUIRES_DOC]->(t:DocumentType)
RETURN f, r, t
