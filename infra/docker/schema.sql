-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Cleanup
DROP TABLE IF EXISTS vectors_esm2_650m CASCADE;
DROP TABLE IF EXISTS vectors_esm2_8m CASCADE;
DROP TABLE IF EXISTS embedding_metadata CASCADE;
DROP TABLE IF EXISTS models CASCADE;

-- Model Registry
CREATE TABLE models (
    model_id VARCHAR(50) PRIMARY KEY,
    family VARCHAR(50),
    parameters_count BIGINT,
    vector_dimension INTEGER NOT NULL,
    quantization_level VARCHAR(10) DEFAULT 'FP32',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE embedding_metadata (
    id SERIAL PRIMARY KEY,
    sequence_hash CHAR(64) NOT NULL,
    model_id VARCHAR(50) NOT NULL REFERENCES models(model_id),
    primary_accession VARCHAR(20),
    protein_name VARCHAR(255),
    organism VARCHAR(100),
    confidence_score FLOAT DEFAULT NULL, 
    is_fallback BOOLEAN DEFAULT FALSE,
    sequence_text TEXT NOT NULL,
    function_text TEXT,
    binding_sites JSONB DEFAULT '[]'::jsonb,
    pdb_ids JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (sequence_hash, model_id)
);

-- Vector Tables
CREATE TABLE vectors_esm2_8m (
    metadata_id INTEGER PRIMARY KEY REFERENCES embedding_metadata(id) ON DELETE CASCADE,
    vector vector(320)
);

CREATE TABLE vectors_esm2_650m (
    metadata_id INTEGER PRIMARY KEY REFERENCES embedding_metadata(id) ON DELETE CASCADE,
    vector vector(1280)
);

-- Indexing
CREATE INDEX idx_vec_8m ON vectors_esm2_8m USING hnsw (vector vector_cosine_ops);
CREATE INDEX idx_vec_650m ON vectors_esm2_650m USING hnsw (vector vector_cosine_ops);
CREATE INDEX idx_meta_accession ON embedding_metadata(primary_accession);
CREATE INDEX idx_meta_organism ON embedding_metadata(organism);

-- Seed Models
INSERT INTO models (model_id, family, parameters_count, vector_dimension) VALUES 
('esm2_t6_8M_UR50D', 'esm2', 8000000, 320), 
('esm2_t33_650M_UR50D', 'esm2', 650000000, 1280);