// Crypto register: jurisdictions, crypto supervisors, laws, public enforcement cases, sanctions lists, and later
// the wallet addresses on those lists. No client data. Built by casefold/build_crypto.py into register/crypto.rl.

// 1. Keys
CREATE CONSTRAINT jurisdiction_code IF NOT EXISTS FOR (n:Jurisdiction) REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT sector_id IF NOT EXISTS FOR (n:Sector) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT regulator_id IF NOT EXISTS FOR (n:Regulator) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT law_id IF NOT EXISTS FOR (n:Law) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT source_id IF NOT EXISTS FOR (n:Source) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT sanctions_list_id IF NOT EXISTS FOR (n:SanctionsList) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT address_key IF NOT EXISTS FOR (n:Address) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT proposal_id IF NOT EXISTS FOR (n:Proposal) REQUIRE n.id IS UNIQUE;

// 2. Required fields and types (Relate, Neo4j Enterprise or Aura), not on Neo4j Community
CREATE CONSTRAINT source_kind IF NOT EXISTS FOR (n:Source) REQUIRE n.kind IS NOT NULL;
CREATE CONSTRAINT source_url IF NOT EXISTS FOR (n:Source) REQUIRE n.url IS NOT NULL;
CREATE CONSTRAINT source_date IF NOT EXISTS FOR (n:Source) REQUIRE n.date IS NOT NULL;
CREATE CONSTRAINT source_amount_type IF NOT EXISTS FOR (n:Source) REQUIRE n.amount :: FLOAT;
CREATE CONSTRAINT source_verify_type IF NOT EXISTS FOR (n:Source) REQUIRE n.verify :: BOOLEAN;
CREATE CONSTRAINT jurisdiction_wave_type IF NOT EXISTS FOR (n:Jurisdiction) REQUIRE n.wave :: INTEGER;
CREATE CONSTRAINT proposal_status IF NOT EXISTS FOR (n:Proposal) REQUIRE n.status IS NOT NULL;

// 3. Indexes
CREATE INDEX source_date_idx IF NOT EXISTS FOR (n:Source) ON (n.date);
CREATE INDEX regulator_short_idx IF NOT EXISTS FOR (n:Regulator) ON (n.short);
CREATE FULLTEXT INDEX crypto_case_text IF NOT EXISTS FOR (n:Source) ON EACH [n.title, n.summary, n.chain, n.party];
