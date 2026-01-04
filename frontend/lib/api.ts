import axios from 'axios';

const API_BASE = '/api/v1'; // Proxied

export interface ProteinMetadata {
  primary_accession: string;
  protein_name: string;
  organism: string;
  is_fallback: boolean;
  model_id: string;
  confidence_score: number;
  vector: number[];
}

export interface StructureManifest {
  accession: string;
  structure: { id: string; url: string; all_pdb_ids: string[]; source: string };
  annotations: { residue_highlights: Array<{ pos: number; label: string }> };
  metadata: { name: string; organism: string; function: string; confidence: number };
}

export const api = {
  getEmbeddings: async (): Promise<ProteinMetadata[]> => {
    const res = await axios.get(`${API_BASE}/embeddings?limit=500`);
    return res.data;
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
  }
};