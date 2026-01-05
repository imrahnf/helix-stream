"""
File Overview: UMAP-based dimensionality reduction engine for turning protein embeddings into 3D graph coordinates.
Responsibilities:
- Standardize high-dimensional vectors and compute 3D UMAP projections with deterministic settings.
- Handle small-sample fallbacks and scale coordinates for visualization ranges.
- Batch persist computed positions to graph_positions with upsert per accession/model/method.
Data Flow:
- Inputs: numpy array of vectors (n x d), accessions list, model_id, reduction params.
- Outputs: numpy array of 3D positions and committed DB rows for stored coordinates.
System Integration:
- Invoked by GraphService and analytics flows before frontend graph rendering; writes via repository connection.
Technical Details:
- Uses sklearn StandardScaler, umap-learn with cosine metric, single-threaded, random_state=42; scales positions around origin.
- Validates vector count, adjusts n_neighbors to dataset size, and randomizes placement for very small sets.
Future Considerations:
- Add progress/telemetry for long running projections.
"""

import numpy as np
import logging
from typing import List, Tuple
from umap import UMAP
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class ProjectionEngine:
    """
    High-performance dimensionality reduction engine for protein embeddings.
    
    Uses UMAP (Uniform Manifold Approximation and Projection) for optimal
    preservation of local and global structure in 3D space.
    """
    
    @staticmethod
    def compute_umap_3d(
        vectors: np.ndarray,
        n_neighbors: int = 15,
        min_dist: float = 0.1,
        metric: str = 'cosine'
    ) -> np.ndarray:
        """
        Reduce high-dimensional vectors to 3D using UMAP.
        
        Args:
            vectors: (n_samples, n_features) array of embedding vectors
            n_neighbors: Number of neighbors for local manifold approximation
                        (higher = more global structure, lower = more local)
            min_dist: Minimum distance between points in low-dimensional space
                     (higher = more spread out, lower = more clustered)
            metric: Distance metric ('cosine' recommended for embeddings)
        
        Returns:
            (n_samples, 3) array of 3D coordinates
        
        Performance:
            - 100 proteins: ~2-5 seconds
            - 500 proteins: ~10-20 seconds  
            - 1000 proteins: ~30-60 seconds
        """
        if len(vectors) == 0:
            logger.warning("Empty vector array provided to UMAP")
            return np.array([])
        
        if len(vectors) < 4:
            logger.warning(f"Only {len(vectors)} vectors provided, UMAP requires n_neighbors >= 2")
            # For very small datasets, use random positioning
            return np.random.randn(len(vectors), 3) * 100
        
        # Adjust n_neighbors if dataset is too small
        n_neighbors = min(n_neighbors, len(vectors) - 1)
        
        logger.info(f"Computing UMAP projection for {len(vectors)} vectors "
                   f"(dim={vectors.shape[1]}) with n_neighbors={n_neighbors}")
        
        try:
            # Standardize features for better numerical stability
            scaler = StandardScaler()
            vectors_scaled = scaler.fit_transform(vectors)
            
            # Configure UMAP for 3D visualization
            reducer = UMAP(
                n_components=3,
                n_neighbors=n_neighbors,
                min_dist=min_dist,
                metric=metric,
                random_state=42,  # Reproducible results
                n_jobs=1,  # Single-threaded for stability
                verbose=False
            )
            
            # Perform dimensionality reduction
            positions_3d = reducer.fit_transform(vectors_scaled)
            
            # Scale coordinates to reasonable viewing range (centered at origin)
            positions_3d = (positions_3d - positions_3d.mean(axis=0)) * 300
            
            logger.info(f"UMAP projection complete. Coordinate range: "
                       f"x=[{positions_3d[:, 0].min():.1f}, {positions_3d[:, 0].max():.1f}], "
                       f"y=[{positions_3d[:, 1].min():.1f}, {positions_3d[:, 1].max():.1f}], "
                       f"z=[{positions_3d[:, 2].min():.1f}, {positions_3d[:, 2].max():.1f}]")
            
            return positions_3d
            
        except Exception as e:
            logger.error(f"UMAP projection failed: {e}", exc_info=True)
            raise
    
    @staticmethod
    def store_positions(
            repo,
            accessions: List[str],
            positions: np.ndarray,
            model_id: str,
            method: str = 'umap'
        ) -> int:
        """
        Batch store 3D positions in database.
        
        Args:
            repo: DatabaseRepository instance
            accessions: List of protein accession IDs
            positions: (n, 3) array of 3D coordinates
            model_id: Model identifier (e.g., 'esm2_t33_650M_UR50D')
            method: Reduction method ('umap', 'tsne', 'pca')
        
        Returns:
            Number of positions stored
        """
        if len(accessions) != len(positions):
            raise ValueError(f"Accession count ({len(accessions)}) != position count ({len(positions)})")
        
        logger.info(f"Storing {len(accessions)} {method.upper()} positions for model {model_id}")
        
        stored_count = 0
        with repo.conn.cursor() as cur:
            for acc, (x, y, z) in zip(accessions, positions):
                try:
                    cur.execute("""
                        INSERT INTO graph_positions (accession, model_id, x, y, z, method)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (accession, model_id, method) 
                        DO UPDATE SET 
                            x = EXCLUDED.x, 
                            y = EXCLUDED.y, 
                            z = EXCLUDED.z, 
                            computed_at = NOW()
                    """, (acc, model_id, float(x), float(y), float(z), method))
                    stored_count += 1
                except Exception as e:
                    logger.error(f"Failed to store position for {acc}: {e}")
                    continue
            
            repo.conn.commit()
        
        logger.info(f"Successfully stored {stored_count}/{len(accessions)} positions")
        return stored_count
