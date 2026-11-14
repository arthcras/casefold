// Sector register. The legislation: per law (Wwft, Sanctiewet 1977, Rtsw, Wft, Wtt 2018, Wok, AVG/UAVG, Handelsregisterwet, MiCA, TFR, ECSPR, AMLR, Iwt, ...), in force on $on or later, the sectors it applies to and whether the link comes from the authority inventory or was added by Casefold.
MATCH (l:Law)<-[r:SUBJECT_TO]-(s:Sector)
RETURN l.short AS law, l.title AS title, coalesce(l.kind, '') AS kind,
       CASE WHEN l.valid_from IS NULL OR l.valid_from <= $on THEN 'in force' ELSE 'from ' + l.valid_from END AS status,
       count(DISTINCT s) AS sectors, collect(DISTINCT r.source) AS source, collect(DISTINCT s.local)[0..6] AS example_sectors
ORDER BY sectors DESC, law
