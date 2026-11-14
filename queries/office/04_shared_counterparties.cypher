// Office file. KYCC across clients: counterparties that recur in more than one of the office's client files. The office file holds only a one-way key per counterparty (from its name and country), so the overlap shows without the name; the name is in the client files.
MATCH (i:Institution)<-[:CLIENT_OF]-(f:ClientFile)-[:HAS_COUNTERPARTY]->(k:CounterpartyKey)
WITH i, k, collect(DISTINCT f.case) AS files
WHERE size(files) > 1
RETURN i.name AS office, k.key AS counterparty_key, size(files) AS client_files, files
ORDER BY client_files DESC
