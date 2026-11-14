// Office file. The office's clients on $on: one row per client file, with what that file says (UBO answer, sector duties that need action, monitoring signals), worst first. The client data stays in the client's own file; the office file holds the file name and the signals only.
MATCH (i:Institution)<-[:CLIENT_OF]-(f:ClientFile)
RETURN i.name AS office, f.case AS client_file, f.file AS file, f.legal_form AS legal_form, f.business_type AS business_type, f.sbi AS sbi, f.risk_band AS risk_band, f.service AS service, f.ubo AS ubo,
       f.actions AS duty_actions, f.monitoring AS monitoring_signals, size(f.actions) + size(f.monitoring) AS signals, f.as_of AS as_of
ORDER BY signals DESC, client_file
