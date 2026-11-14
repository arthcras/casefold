// Office file: the office, the duties of its sector, what it recorded, and per client a summary without names.

// 1. Keys
CREATE CONSTRAINT institution_id IF NOT EXISTS FOR (n:Institution) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT sector_id IF NOT EXISTS FOR (n:Sector) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT category_id IF NOT EXISTS FOR (n:SectorCategory) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT fatf_id IF NOT EXISTS FOR (n:FatfScope) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT regulator_id IF NOT EXISTS FOR (n:Regulator) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT licence_id IF NOT EXISTS FOR (n:Licence) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT law_id IF NOT EXISTS FOR (n:Law) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT article_id IF NOT EXISTS FOR (n:Article) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT duty_id IF NOT EXISTS FOR (n:SectorDuty) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT record_id IF NOT EXISTS FOR (n:OfficeRecord) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT client_file_id IF NOT EXISTS FOR (n:ClientFile) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT client_file_case IF NOT EXISTS FOR (n:ClientFile) REQUIRE n.case IS UNIQUE;
CREATE CONSTRAINT counterparty_key IF NOT EXISTS FOR (n:CounterpartyKey) REQUIRE n.key IS UNIQUE;

// 2. Required fields and types (Relate, Neo4j Enterprise/Aura)
CREATE CONSTRAINT record_date IF NOT EXISTS FOR (n:OfficeRecord) REQUIRE n.date IS NOT NULL;
CREATE CONSTRAINT record_duty IF NOT EXISTS FOR (n:OfficeRecord) REQUIRE n.duty IS NOT NULL;
CREATE CONSTRAINT client_file_as_of IF NOT EXISTS FOR (n:ClientFile) REQUIRE n.as_of IS NOT NULL;
CREATE CONSTRAINT client_file_file IF NOT EXISTS FOR (n:ClientFile) REQUIRE n.file IS NOT NULL;
CREATE CONSTRAINT counterparty_key_type IF NOT EXISTS FOR (n:CounterpartyKey) REQUIRE n.key :: STRING;
CREATE CONSTRAINT duty_from IF NOT EXISTS FOR (n:SectorDuty) REQUIRE n.valid_from IS NOT NULL;
CREATE CONSTRAINT supervises_aml_type IF NOT EXISTS FOR ()-[r:SUPERVISES]-() REQUIRE r.aml :: BOOLEAN;

// 3. Indexes
CREATE INDEX record_date_idx IF NOT EXISTS FOR (n:OfficeRecord) ON (n.date);
CREATE INDEX client_file_risk IF NOT EXISTS FOR (n:ClientFile) ON (n.risk_band);
CREATE INDEX duty_valid IF NOT EXISTS FOR (n:SectorDuty) ON (n.valid_from, n.valid_to);
