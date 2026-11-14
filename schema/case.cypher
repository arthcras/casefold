// Client file: the client, its structure, documents, transactions, KYCC, the rules applied and the reasoning.

// 1. Keys
CREATE CONSTRAINT case_id IF NOT EXISTS FOR (n:Case) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT client_id IF NOT EXISTS FOR (n:Client) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT party_id IF NOT EXISTS FOR (n:Party) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT institution_id IF NOT EXISTS FOR (n:Institution) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT document_id IF NOT EXISTS FOR (n:Document) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT proposal_id IF NOT EXISTS FOR (n:Proposal) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT proposal_status IF NOT EXISTS FOR (n:Proposal) REQUIRE n.status IS NOT NULL;
CREATE CONSTRAINT proposal_status_type IF NOT EXISTS FOR (n:Proposal) REQUIRE n.status :: STRING;
CREATE CONSTRAINT question_id IF NOT EXISTS FOR (n:Question) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT signal_id IF NOT EXISTS FOR (n:Signal) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT service_id IF NOT EXISTS FOR (n:Service) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT transaction_id IF NOT EXISTS FOR (n:Transaction) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT counterparty_id IF NOT EXISTS FOR (n:Counterparty) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT country_code IF NOT EXISTS FOR (n:Country) REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT screening_hit_id IF NOT EXISTS FOR (n:ScreeningHit) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT jurisdiction_code IF NOT EXISTS FOR (n:Jurisdiction) REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT sector_id IF NOT EXISTS FOR (n:Sector) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT category_id IF NOT EXISTS FOR (n:SectorCategory) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT fatf_id IF NOT EXISTS FOR (n:FatfScope) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT regulator_id IF NOT EXISTS FOR (n:Regulator) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT licence_id IF NOT EXISTS FOR (n:Licence) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT law_id IF NOT EXISTS FOR (n:Law) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT article_id IF NOT EXISTS FOR (n:Article) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT duty_id IF NOT EXISTS FOR (n:SectorDuty) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT monitoring_rule_id IF NOT EXISTS FOR (n:MonitoringRule) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT obligation_key IF NOT EXISTS FOR (n:Obligation) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT document_type_key IF NOT EXISTS FOR (n:DocumentType) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT legal_form_id IF NOT EXISTS FOR (n:LegalForm) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT risk_trigger_key IF NOT EXISTS FOR (n:RiskTrigger) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT business_type_code IF NOT EXISTS FOR (n:BusinessType) REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT risk_factor_id IF NOT EXISTS FOR (n:RiskFactor) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT ubo_rule_id IF NOT EXISTS FOR (n:UboRule) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT ubo_ground_id IF NOT EXISTS FOR (n:UboGround) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT ground_type_key IF NOT EXISTS FOR (n:GroundType) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT session_id IF NOT EXISTS FOR (n:Session) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT ask_id IF NOT EXISTS FOR (n:Ask) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT answer_id IF NOT EXISTS FOR (n:Answer) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT step_id IF NOT EXISTS FOR (n:Step) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (n:Claim) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT tool_call_id IF NOT EXISTS FOR (n:ToolCall) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT episode_id IF NOT EXISTS FOR (n:Episode) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT pattern_id IF NOT EXISTS FOR (n:Pattern) REQUIRE n.id IS UNIQUE;

// 2. Required fields and types (Relate, Neo4j Enterprise/Aura)
CREATE CONSTRAINT client_name IF NOT EXISTS FOR (n:Client) REQUIRE n.name IS NOT NULL;
CREATE CONSTRAINT party_name IF NOT EXISTS FOR (n:Party) REQUIRE n.name IS NOT NULL;
CREATE CONSTRAINT party_pep_type IF NOT EXISTS FOR (n:Party) REQUIRE n.pep :: BOOLEAN;
CREATE CONSTRAINT transaction_amount IF NOT EXISTS FOR (n:Transaction) REQUIRE n.amount IS NOT NULL;
CREATE CONSTRAINT transaction_amount_type IF NOT EXISTS FOR (n:Transaction) REQUIRE n.amount :: INTEGER | FLOAT;
CREATE CONSTRAINT transaction_date IF NOT EXISTS FOR (n:Transaction) REQUIRE n.date IS NOT NULL;
CREATE CONSTRAINT transaction_date_type IF NOT EXISTS FOR (n:Transaction) REQUIRE n.date :: STRING;
CREATE CONSTRAINT transaction_currency IF NOT EXISTS FOR (n:Transaction) REQUIRE n.currency IS NOT NULL;
CREATE CONSTRAINT counterparty_role IF NOT EXISTS FOR (n:Counterparty) REQUIRE n.role IS NOT NULL;
CREATE CONSTRAINT country_high_risk_type IF NOT EXISTS FOR (n:Country) REQUIRE n.high_risk :: BOOLEAN;
CREATE CONSTRAINT document_title IF NOT EXISTS FOR (n:Document) REQUIRE n.title IS NOT NULL;
CREATE CONSTRAINT owns_pct_type IF NOT EXISTS FOR ()-[r:OWNS]-() REQUIRE r.pct :: INTEGER | FLOAT;
CREATE CONSTRAINT counterparty_of_role IF NOT EXISTS FOR ()-[r:COUNTERPARTY_OF]-() REQUIRE r.role IS NOT NULL;
CREATE CONSTRAINT duty_from IF NOT EXISTS FOR (n:SectorDuty) REQUIRE n.valid_from IS NOT NULL;
CREATE CONSTRAINT supervises_aml_type IF NOT EXISTS FOR ()-[r:SUPERVISES]-() REQUIRE r.aml :: BOOLEAN;
CREATE CONSTRAINT claim_status IF NOT EXISTS FOR (n:Claim) REQUIRE n.status IS NOT NULL;
CREATE CONSTRAINT pattern_status IF NOT EXISTS FOR (n:Pattern) REQUIRE n.status IS NOT NULL;

// 3. Indexes
CREATE INDEX transaction_date_idx IF NOT EXISTS FOR (n:Transaction) ON (n.date);
CREATE INDEX counterparty_key_idx IF NOT EXISTS FOR (n:Counterparty) ON (n.key);
CREATE INDEX counterparty_country IF NOT EXISTS FOR (n:Counterparty) ON (n.country);
CREATE INDEX duty_valid IF NOT EXISTS FOR (n:SectorDuty) ON (n.valid_from, n.valid_to);
CREATE INDEX ask_at IF NOT EXISTS FOR (n:Ask) ON (n.at);
CREATE TEXT INDEX party_name_text IF NOT EXISTS FOR (n:Party) ON (n.name);
CREATE TEXT INDEX counterparty_name_text IF NOT EXISTS FOR (n:Counterparty) ON (n.name);
CREATE FULLTEXT INDEX doc_text IF NOT EXISTS FOR (n:Document) ON EACH [n.title, n.text];
CREATE FULLTEXT INDEX article_text IF NOT EXISTS FOR (n:Article) ON EACH [n.text_en, n.text_local];
CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (n:Chunk) ON EACH [n.text];
