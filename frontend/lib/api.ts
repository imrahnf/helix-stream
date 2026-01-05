import axios from 'axios';

const API_BASE = '/api/v1'; // Proxied

export interface ProteinMetadata {
  primary_accession: string;
  protein_name: string;
  organism: string;
  is_fallback: boolean;
  model_id: string;
  confidence_score: number;
  x?: number;  // 3D position from backend
  y?: number;
  z?: number;
  vector?: number[];  // Only used during migration, will be removed
}

export interface NeighborData {
  primary_accession: string;
  protein_name: string;
  organism: string;
  confidence_score: number;
  is_fallback: boolean;
  similarity: number;
  rank: number;
}

export interface StructureManifest {
  accession: string;
  structure: { id: string; url: string; all_pdb_ids: string[]; source: string };
  annotations: { residue_highlights: Array<{ pos: number; label: string }> };
  metadata: { name: string; organism: string; function: string; confidence: number; sequence?: string };
}

export interface StatusResponse {
  status: string;
  latency_ms: number;
  timestamp: string;
}

export const api = {
  /**
   * Get paginated list of proteins with backend-computed 3D positions.
   * Replaces getEmbeddings() with optimized payload (no vectors).
   */
  getProteins: async (params?: {
    limit?: number;
    offset?: number;
    search?: string;
    min_confidence?: number;
    organism?: string;
    include_fallback?: boolean;
    method?: 'umap' | 'tsne' | 'pca';
  }): Promise<{ data: ProteinMetadata[]; total: number; limit: number; offset: number }> => {
    try {
      const queryParams = new URLSearchParams();
      if (params?.limit) queryParams.append('limit', params.limit.toString());
      if (params?.offset) queryParams.append('offset', params.offset.toString());
      if (params?.search) queryParams.append('search', params.search);
      if (params?.min_confidence) queryParams.append('min_confidence', params.min_confidence.toString());
      if (params?.organism) queryParams.append('organism', params.organism);
      if (params?.include_fallback !== undefined) queryParams.append('include_fallback', params.include_fallback.toString());
      if (params?.method) queryParams.append('method', params.method);
      
      const res = await axios.get(`${API_BASE}/proteins?${queryParams.toString()}`, { timeout: 10000 });
      return res.data;
    } catch (error) {
      console.error('Failed to fetch proteins:', error);
      return { data: [], total: 0, limit: 100, offset: 0 };
    }
  },

  /**
   * Legacy method for backward compatibility during migration.
   * Use getProteins() for new code.
   */
  getEmbeddings: async (): Promise<ProteinMetadata[]> => {
    try {
      const result = await api.getProteins({ limit: 500 });
      return result.data;
    } catch (error) {
      console.error('Failed to fetch embeddings:', error);
      return [];
    }
  },

  /**
   * Get pre-computed K-nearest neighbors from backend.
   * Ultra-fast O(1) lookup (<5ms).
   */
  getNeighbors: async (accession: string, limit: number = 10): Promise<NeighborData[]> => {
    try {
      const res = await axios.get(`${API_BASE}/neighbors/${accession}?limit=${limit}`, { timeout: 15000 });
      return res.data.neighbors || [];
    } catch (error) {
      console.error(`Failed to fetch neighbors for ${accession}:`, error);
      return [];
    }
  },

  /**
   * Get similarity score between two proteins with caching.
   * Returns cached result if available (<1ms), computes if needed (~10ms).
   */
  getSimilarity: async (acc1: string, acc2: string): Promise<number> => {
    try {
      const res = await axios.get(`${API_BASE}/similarity/${acc1}/${acc2}`, { timeout: 5000 });
      return res.data.similarity || 0;
    } catch (error) {
      console.error(`Failed to fetch similarity for ${acc1} <-> ${acc2}:`, error);
      return 0;
    }
  },

  /**
   * Trigger backend computation of 3D graph positions using UMAP.
   * Run once after bulk ingestion or when positions are missing.
   */
  computeLayout: async (method: 'umap' | 'tsne' | 'pca' = 'umap', forceRecompute: boolean = false): Promise<any> => {
    try {
      const res = await axios.post(
        `${API_BASE}/compute-layout?method=${method}&force_recompute=${forceRecompute}`,
        {},
        { timeout: 120000 }  // 2 minute timeout for large computations
      );
      return res.data;
    } catch (error) {
      console.error('Failed to compute layout:', error);
      throw error;
    }
  },

  getStructure: async (acc: string): Promise<StructureManifest> => {
    const res = await axios.get(`${API_BASE}/structure/${acc}`);
    return res.data;
  },
  search: async (seq: string) => {
    const res = await axios.post(`${API_BASE}/search`, { sequence: seq });
    return res.data;
  },
  ingest: async (input: string) => {
    // Detect if input is a UniProt/PDB accession (short ID) or a FASTA sequence
    const isAccession = /^[A-Z0-9]{1,10}$/.test(input.trim());
    if (isAccession) {
      // Route accession IDs to ingest_from_uniprot for full metadata
      const res = await axios.post(`${API_BASE}/ingest?query=${encodeURIComponent(input.trim())}`);
      return res.data;
    } else {
      // Route FASTA sequences to ingest_manual_sequence
      const res = await axios.post(`${API_BASE}/ingest`, { sequence: input });
      return res.data;
    }
  },
  getStatus: async (): Promise<StatusResponse> => {
    const res = await axios.get(`${API_BASE}/status`);
    return res.data;
  }
};