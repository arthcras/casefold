// Sector register: jurisdiction -> sector -> authorities, licences, laws, duties. No client data.

// 1. Keys
CREATE CONSTRAINT jurisdiction_code IF NOT EXISTS FOR (n:Jurisdiction) REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT sector_id IF NOT EXISTS FOR (n:Sector) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT category_id IF NOT EXISTS FOR (n:SectorCategory) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT fatf_id IF NOT EXISTS FOR (n:FatfScope) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT regulator_id IF NOT EXISTS FOR (n:Regulator) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT regulator_short IF NOT EXISTS FOR (n:Regulator) REQUIRE n.short IS UNIQUE;
CREATE CONSTRAINT licence_id IF NOT EXISTS FOR (n:Licence) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT law_id IF NOT EXISTS FOR (n:Law) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT article_id IF NOT EXISTS FOR (n:Article) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT duty_id IF NOT EXISTS FOR (n:SectorDuty) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT business_type_code IF NOT EXISTS FOR (n:BusinessType) REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT risk_factor_id IF NOT EXISTS FOR (n:RiskFactor) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT office_file_id IF NOT EXISTS FOR (n:OfficeFile) REQUIRE n.id IS UNIQUE;

// 2. Required fields and types (Relate, Neo4j Enterprise/Aura)
CREATE CONSTRAINT sector_name IF NOT EXISTS FOR (n:Sector) REQUIRE n.name IS NOT NULL;
CREATE CONSTRAINT sector_status IF NOT EXISTS FOR (n:Sector) REQUIRE n.status IS NOT NULL;
CREATE CONSTRAINT sector_status_type IF NOT EXISTS FOR (n:Sector) REQUIRE n.status :: STRING;
CREATE CONSTRAINT regulator_name IF NOT EXISTS FOR (n:Regulator) REQUIRE n.name IS NOT NULL;
CREATE CONSTRAINT duty_title IF NOT EXISTS FOR (n:SectorDuty) REQUIRE n.title IS NOT NULL;
CREATE CONSTRAINT duty_kind IF NOT EXISTS FOR (n:SectorDuty) REQUIRE n.kind IS NOT NULL;
CREATE CONSTRAINT duty_from IF NOT EXISTS FOR (n:SectorDuty) REQUIRE n.valid_from IS NOT NULL;
CREATE CONSTRAINT duty_from_type IF NOT EXISTS FOR (n:SectorDuty) REQUIRE n.valid_from :: STRING;
CREATE CONSTRAINT duty_to_type IF NOT EXISTS FOR (n:SectorDuty) REQUIRE n.valid_to :: STRING;
CREATE CONSTRAINT duty_independent_type IF NOT EXISTS FOR (n:SectorDuty) REQUIRE n.independent :: BOOLEAN;
CREATE CONSTRAINT supervises_role IF NOT EXISTS FOR ()-[r:SUPERVISES]-() REQUIRE r.role IS NOT NULL;
CREATE CONSTRAINT supervises_aml IF NOT EXISTS FOR ()-[r:SUPERVISES]-() REQUIRE r.aml IS NOT NULL;
CREATE CONSTRAINT supervises_aml_type IF NOT EXISTS FOR ()-[r:SUPERVISES]-() REQUIRE r.aml :: BOOLEAN;

// 3. Indexes
CREATE INDEX law_short IF NOT EXISTS FOR (n:Law) ON (n.short);
CREATE INDEX duty_kind_idx IF NOT EXISTS FOR (n:SectorDuty) ON (n.kind);
CREATE INDEX duty_valid IF NOT EXISTS FOR (n:SectorDuty) ON (n.valid_from, n.valid_to);
CREATE INDEX sector_status_idx IF NOT EXISTS FOR (n:Sector) ON (n.status);
CREATE INDEX supervises_aml_idx IF NOT EXISTS FOR ()-[r:SUPERVISES]-() ON (r.aml);
CREATE FULLTEXT INDEX duty_text IF NOT EXISTS FOR (n:SectorDuty) ON EACH [n.title, n.text];
CREATE FULLTEXT INDEX article_text IF NOT EXISTS FOR (n:Article) ON EACH [n.text_en, n.text_local];
