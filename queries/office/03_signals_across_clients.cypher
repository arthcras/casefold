// Office file. Which signals recur across the office's clients: per monitoring signal or duty action, how many client files show it and which. A view for the compliance officer and the supervisor's periodic return.
MATCH (i:Institution)<-[:CLIENT_OF]-(f:ClientFile)
UNWIND [x IN f.monitoring | 'monitoring: ' + x] + [x IN f.actions | 'duty: ' + x] AS signal
RETURN i.name AS office, signal, count(DISTINCT f) AS client_files, collect(DISTINCT f.case) AS files
ORDER BY client_files DESC, signal
