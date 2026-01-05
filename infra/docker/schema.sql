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
    primary_accession VARCHAR(20) UNIQUE NOT NULL,  -- Added UNIQUE constraint
    protein_name VARCHAR(255),
    organism VARCHAR(100),
    confidence_score FLOAT DEFAULT NULL, 
    is_fallback BOOLEAN DEFAULT FALSE,
    sequence_text TEXT NOT NULL,
    function_text TEXT,
    binding_sites JSONB DEFAULT '[]'::jsonb,
    pdb_ids JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
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

-- ============================================================================
-- PERFORMANCE OPTIMIZATION TABLES
-- ============================================================================

-- Pre-computed K-Nearest Neighbor (KNN) Graph Edges
-- Stores top-N most similar proteins for O(1) neighbor lookup
CREATE TABLE IF NOT EXISTS graph_edges (
    id SERIAL PRIMARY KEY,
    source_accession VARCHAR(20) NOT NULL,
    target_accession VARCHAR(20) NOT NULL,
    similarity FLOAT NOT NULL CHECK (similarity >= 0 AND similarity <= 1),
    rank INTEGER NOT NULL CHECK (rank > 0),
    model_id VARCHAR(50) NOT NULL REFERENCES models(model_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_accession, target_accession, model_id),
    FOREIGN KEY (source_accession) REFERENCES embedding_metadata(primary_accession) ON DELETE CASCADE,
    FOREIGN KEY (target_accession) REFERENCES embedding_metadata(primary_accession) ON DELETE CASCADE
);

-- Pre-computed 3D Positions for Graph Visualization
-- Stores dimensionality-reduced coordinates (UMAP/t-SNE/PCA)
CREATE TABLE IF NOT EXISTS graph_positions (
    accession VARCHAR(20) NOT NULL,
    model_id VARCHAR(50) NOT NULL REFERENCES models(model_id),
    x FLOAT NOT NULL,
    y FLOAT NOT NULL,
    z FLOAT NOT NULL,
    method VARCHAR(20) NOT NULL CHECK (method IN ('umap', 'tsne', 'pca')),
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (accession, model_id, method),
    FOREIGN KEY (accession) REFERENCES embedding_metadata(primary_accession) ON DELETE CASCADE
);

-- Similarity Cache for Protein Comparisons
-- Stores pairwise similarity scores to avoid recomputation
CREATE TABLE IF NOT EXISTS similarity_cache (
    protein_a VARCHAR(20) NOT NULL,
    protein_b VARCHAR(20) NOT NULL,
    similarity FLOAT NOT NULL CHECK (similarity >= 0 AND similarity <= 1),
    model_id VARCHAR(50) NOT NULL REFERENCES models(model_id),
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (protein_a, protein_b, model_id),
    CHECK (protein_a < protein_b),  -- Enforce ordering to prevent duplicates
    FOREIGN KEY (protein_a) REFERENCES embedding_metadata(primary_accession) ON DELETE CASCADE,
    FOREIGN KEY (protein_b) REFERENCES embedding_metadata(primary_accession) ON DELETE CASCADE
);

-- ============================================================================
-- PERFORMANCE INDEXES
-- ============================================================================

-- Graph edges indexes for fast neighbor lookup
CREATE INDEX IF NOT EXISTS idx_graph_source_rank ON graph_edges(source_accession, model_id, rank);
CREATE INDEX IF NOT EXISTS idx_graph_target ON graph_edges(target_accession, model_id);

-- Position lookup index
CREATE INDEX IF NOT EXISTS idx_positions_model ON graph_positions(model_id, method);

-- Similarity cache index
CREATE INDEX IF NOT EXISTS idx_similarity_model ON similarity_cache(model_id);

-- Full-text search index for protein names
CREATE INDEX IF NOT EXISTS idx_protein_name_gin ON embedding_metadata USING gin(to_tsvector('english', protein_name));

-- Additional filtering indexes
CREATE INDEX IF NOT EXISTS idx_confidence ON embedding_metadata(confidence_score);
CREATE INDEX IF NOT EXISTS idx_fallback ON embedding_metadata(is_fallback);
CREATE INDEX IF NOT EXISTS idx_organism_conf ON embedding_metadata(organism, confidence_score);