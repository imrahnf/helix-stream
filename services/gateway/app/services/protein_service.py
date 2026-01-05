"""
File Overview: Protein listing and filtering service backing HelixStream frontend queries.
Responsibilities:
- Build parameterized queries for paginated protein metadata filtered by search text, confidence, organism, and fallback flags.
- Join graph_positions for layout coordinates and optionally include fallback model entries.
- Provide embedding retrieval with safe JSON decoding of stored vectors.
Data Flow:
- Inputs: limit/offset, search terms, min_confidence, organism, include_fallback flag, method, model_id; repository cursor.
- Outputs: dict with data rows and total count; list of embeddings with vectors parsed to native lists.
System Integration:
- Used by FastAPI endpoints to serve table and graph data; queries embedding_metadata and graph_positions via repository connection.
Technical Details:
- Uses RealDictCursor for dict rows; replaces select clause for count to avoid re-writing filters; decodes JSON vector strings.
Future Considerations:
- Harden dynamic SQL replacements, align indexes with filter fields, and add server-side sorting customization.
"""

import json
from typing import Dict, Optional
from psycopg2.extras import RealDictCursor

# Handles protein queries, search, and filtering
class ProteinService:
    def __init__(self, repository):
        self.repo = repository
    
    def get_proteins(
            self,
            limit: int,
            offset: int,
            search: Optional[str],
            min_confidence: float,
            organism: Optional[str],
            include_fallback: bool,
            method: str,
            model_id: str
        ) -> Dict:
        
        cur = self.repo.conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT m.primary_accession, m.protein_name, m.organism, 
                   m.confidence_score, m.is_fallback, m.model_id, p.x, p.y, p.z
            FROM embedding_metadata m
            LEFT JOIN graph_positions p ON m.primary_accession = p.accession 
                AND p.method = %s
            WHERE (m.model_id = %s OR m.model_id = 'esm2_t6_8M_UR50D')
        """
        params = [method, model_id]
        
        if search:
            query += " AND (m.protein_name ILIKE %s OR m.primary_accession ILIKE %s OR m.organism ILIKE %s)"
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern, search_pattern])
        
        if min_confidence > 0:
            query += " AND m.confidence_score >= %s"
            params.append(min_confidence)
        
        if organism:
            query += " AND m.organism = %s"
            params.append(organism)
        
        if not include_fallback:
            query += " AND m.is_fallback = FALSE"
        
        count_query = query.replace(
            "SELECT m.primary_accession, m.protein_name, m.organism, m.confidence_score, m.is_fallback, m.model_id, p.x, p.y, p.z",
            "SELECT COUNT(*)"
        )
        cur.execute(count_query, params)
        result = cur.fetchone()
        total = list(result.values())[0] if result else 0
        
        query += " ORDER BY m.confidence_score DESC NULLS LAST LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cur.execute(query, params)
        results = cur.fetchall()
        
        return {"data": results, "total": total, "limit": limit, "offset": offset}
    
    def get_embeddings(self, limit: int):
        results = self.repo.get_all_summaries(limit)
        
        for r in results:
            if isinstance(r['vector'], str):
                r['vector'] = json.loads(r['vector'])
        
        return results
