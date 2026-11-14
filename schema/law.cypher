// Law file: one law, one version, one language, read in by casefold/law_ingest.py. No client data.

// 1. Keys
CREATE CONSTRAINT law_version_id IF NOT EXISTS FOR (n:LawVersion) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT law_article_id IF NOT EXISTS FOR (n:LawArticle) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT law_paragraph_id IF NOT EXISTS FOR (n:LawParagraph) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT law_point_id IF NOT EXISTS FOR (n:LawPoint) REQUIRE n.id IS UNIQUE;

// 2. Required fields and types (Relate, Neo4j Enterprise/Aura)
CREATE CONSTRAINT law_version_sha IF NOT EXISTS FOR (n:LawVersion) REQUIRE n.sha256 IS NOT NULL;
CREATE CONSTRAINT law_version_from IF NOT EXISTS FOR (n:LawVersion) REQUIRE n.valid_from IS NOT NULL;
CREATE CONSTRAINT law_article_number IF NOT EXISTS FOR (n:LawArticle) REQUIRE n.number IS NOT NULL;
CREATE CONSTRAINT law_article_text IF NOT EXISTS FOR (n:LawArticle) REQUIRE n.text :: STRING;

// 3. Indexes
CREATE INDEX law_article_number_idx IF NOT EXISTS FOR (n:LawArticle) ON (n.number);
CREATE FULLTEXT INDEX law_text IF NOT EXISTS FOR (n:LawArticle) ON EACH [n.heading, n.text];
CREATE FULLTEXT INDEX law_paragraph_text IF NOT EXISTS FOR (n:LawParagraph) ON EACH [n.text];
