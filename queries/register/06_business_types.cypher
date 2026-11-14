// Sector register. Business typologies of clients: activity code (SBI 2008 / NACE rev. 2) and the risk factors from Annex II (lower risk) and Annex III (higher risk) of the fourth AML directive, and the risk band that follows (higher, lower or standard).
MATCH (t:BusinessType)
OPTIONAL MATCH (t)-[:HAS_RISK_FACTOR]->(r:RiskFactor)
WITH t, collect(r) AS fs
RETURN t.name_nl AS business_type, t.sbi AS sbi, [f IN fs | f.id + ': ' + f.text] AS risk_factors,
       CASE WHEN any(f IN fs WHERE f.annex = 'III') THEN 'higher: enhanced CDD' WHEN size(fs) > 0 THEN 'lower: simplified CDD possible' ELSE 'standard' END AS risk_band
ORDER BY risk_band, business_type
