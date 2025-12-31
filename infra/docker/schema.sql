-- 1. Setup Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Model Registry
CREATE TABLE IF NOT EXISTS models (
    model_id VARCHAR(50) PRIMARY KEY,
    family VARCHAR(50),
    parameters_count BIGINT,
    vector_dimension INTEGER NOT NULL,
    quantization_level VARCHAR(10) DEFAULT 'FP32',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO models (model_id, family, parameters_count, vector_dimension)
VALUES 
('esm2_t6_8M_UR50D', 'esm2', 8000000, 320),
('esm2_t33_650M_UR50D', 'esm2', 650000000, 1280)
ON CONFLICT (model_id) DO NOTHING;

-- 3. Inference Jobs (source of truth)
-- This table tracks EVERYTHING. Frontend queries this one.
CREATE TABLE IF NOT EXISTS inference_jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sequence_hash CHAR(64) NOT NULL,
    model_id VARCHAR(50) REFERENCES models(model_id),
    status VARCHAR(20) DEFAULT 'PENDING',
    compute_node VARCHAR(50),
    execution_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Result Metadata (lightweight store)
-- Stores confidence, fallback flags, and raw JSON. 
CREATE TABLE IF NOT EXISTS embedding_metadata (
    id SERIAL PRIMARY KEY,
    sequence_hash CHAR(64) NOT NULL,
    model_id VARCHAR(50) NOT NULL REFERENCES models(model_id),
    confidence_score FLOAT,
    is_fallback BOOLEAN DEFAULT FALSE,
    raw_json JSONB, -- Flexible storage for frontend (traits, pI, etc.)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (sequence_hash, model_id)
);

-- 5. Specialized Vector Tables
-- These allow strict HNSW indexing because they are separate tables.

-- Table for 8M (320-D)
CREATE TABLE IF NOT EXISTS vectors_esm2_8m (
    metadata_id INTEGER PRIMARY KEY REFERENCES embedding_metadata(id) ON DELETE CASCADE,
    vector vector(320) -- Strict 320-D
);

-- Table for 650M (1280-D)
CREATE TABLE IF NOT EXISTS vectors_esm2_650m (
    metadata_id INTEGER PRIMARY KEY REFERENCES embedding_metadata(id) ON DELETE CASCADE,
    vector vector(1280) -- Strict 1280-D
);

-- 6. HNSW Indexes
CREATE INDEX idx_vec_8m ON vectors_esm2_8m USING hnsw (vector vector_cosine_ops);
CREATE INDEX idx_vec_650m ON vectors_esm2_650m USING hnsw (vector vector_cosine_ops);