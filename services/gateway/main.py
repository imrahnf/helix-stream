# services/gateway/main.py
import time
import logging
import asyncio
from typing import Dict, Optional
from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware

from app.core.orchestrator import HelixOrchestrator
from app.core.metrics import track_query_time
from app.db.repository import DatabaseContext
from app.services.graph_service import GraphService
from app.services.protein_service import ProteinService
from app.services.similarity_service import SimilarityService
from app.services.comparison_service import ComparisonService

logger = logging.getLogger(__name__)

app = FastAPI(title="HelixStream Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = HelixOrchestrator()

# Auto recomputation tracking for debounced graph updates
pending_recomputation = {
    "count": 0,
    "threshold": 1,
    "task": None
}

async def trigger_graph_recompute():
    # Auto recompute graph positions and edges after threshold of new proteins
    await asyncio.sleep(10)  # Debounce to batch multiple ingestions
    
    if pending_recomputation["count"] >= pending_recomputation["threshold"]:
        try:
            model_id = "esm2_t33_650M_UR50D"
            logger.info(f"Auto-recomputing graph after {pending_recomputation['count']} new proteins")
            
            with DatabaseContext(orchestrator.db_url) as repo:
                missing = repo.get_proteins_without_positions(model_id)
                if missing > 0:
                    logger.info(f"Found {missing} proteins without positions")
                    service = GraphService(repo)
                    result = service.initialize_graph_data(model_id)
                    if "error" not in result:
                        logger.info(f"Graph recomputation complete: {result}")
                    else:
                        logger.warning(f"Graph recomputation issue: {result}")
            
            pending_recomputation["count"] = 0
        except Exception as e:
            logger.error(f"Graph recomputation failed: {e}", exc_info=True)
        finally:
            pending_recomputation["task"] = None

@app.post("/v1/ingest")
async def ingest_data(
        query: Optional[str] = Query(None),
        sequence: Optional[str] = Body(None, embed=True),
        limit: int = 5,
        model_id: str = "esm2_t33_650M_UR50D"
    ):
    clean_sequence = sequence.strip() if sequence else None
    clean_query = query.strip() if query else None
    
    if not clean_sequence and not clean_query:
        raise HTTPException(status_code=400, detail="Missing 'query' or 'sequence' parameter")
    
    try:
        if clean_sequence and len(clean_sequence) > 10:
            result = await orchestrator.ingest_manual_sequence(clean_sequence, model_id)
            pending_recomputation["count"] += 1
        elif clean_query:
            result = await orchestrator.ingest_from_uniprot(clean_query, model_id, limit)
            pending_recomputation["count"] += len(result) if isinstance(result, list) else 1
        else:
            raise HTTPException(status_code=400, detail="Sequence too short (minimum 10 characters)")
        
        # Trigger debounced recomputation if threshold reached
        if pending_recomputation["count"] >= pending_recomputation["threshold"]:
            if pending_recomputation["task"] is None or pending_recomputation["task"].done():
                pending_recomputation["task"] = asyncio.create_task(trigger_graph_recompute())
                logger.info(f"📊 Queued graph recomputation ({pending_recomputation['count']} new proteins)")
        
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.post("/v1/search")
async def search_similar(
    payload: Dict[str, str] = Body(...),
    model_id: str = Query("esm2_t33_650M_UR50D"),
    limit: int = 5
):
    sequence = payload.get("sequence")
    if not sequence:
        raise HTTPException(status_code=422, detail="Missing 'sequence'")
    return await orchestrator.search_similar(sequence, model_id, limit)

@app.get("/v1/structure/{accession}")
async def get_structure(accession: str, model_id: str = Query("esm2_t33_650M_UR50D")):
    manifest = await orchestrator.get_structure_data(accession, model_id)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Protein {accession} not found")
    return manifest


@app.get("/v1/embeddings")
async def get_embeddings(limit: int = 1000):
    with DatabaseContext(orchestrator.db_url) as repo:
        service = ProteinService(repo)
        return service.get_embeddings(limit)


@app.get("/v1/status")
async def get_system_status():
    local_status = "READY"
    remote_status = "OFFLINE"
    latency_ms = 0
    
    try:
        start = time.time()
        if orchestrator._is_worker_online():
            remote_status = "ONLINE"
            latency_ms = int((time.time() - start) * 1000)
    except Exception:
        remote_status = "OFFLINE"
    
    return {
        "workers": {
            "remote": {"status": remote_status, "device": "RX 6800", "type": "GPU"},
            "local": {"status": local_status, "device": "M2", "type": "CPU"}
        },
        "latency_ms": latency_ms,
        "current_mode": "REMOTE" if remote_status == "ONLINE" else "LOCAL_FALLBACK",
        "pipeline_mode": "HYBRID_FAILOVER"
    }

@app.get("/v1/neighbors/{accession}")
@track_query_time("get_neighbors")
async def get_neighbors(
        accession: str,
        model_id: str = Query("esm2_t33_650M_UR50D"),
        limit: int = Query(10, ge=1, le=50)
    ):
    with DatabaseContext(orchestrator.db_url) as repo:
        service = GraphService(repo)
        result = service.get_neighbors(accession, model_id, limit)
        
        if result is None:
            raise HTTPException(status_code=404, detail=f"Protein {accession} not found")
        return result


# Note: /compare is the new endpoint- keeping this for backup
@app.get("/v1/similarity/{acc1}/{acc2}")
@track_query_time("get_similarity")
async def get_similarity(
    acc1: str,
    acc2: str,
    model_id: str = Query("esm2_t33_650M_UR50D")
):
    with DatabaseContext(orchestrator.db_url) as repo:
        service = SimilarityService(repo)
        return service.get_similarity(acc1, acc2, model_id)


@app.get("/v1/compare/{acc1}/{acc2}")
@track_query_time("compare_proteins")
async def compare_proteins(
        acc1: str,
        acc2: str,
        model_id: str = Query("esm2_t33_650M_UR50D")
    ):
    with DatabaseContext(orchestrator.db_url) as repo:
        service = ComparisonService(repo)
        return service.compare_detailed(acc1, acc2, model_id)


@app.post("/v1/compute-layout")
@track_query_time("compute_layout")
async def compute_layout(
        model_id: str = Query("esm2_t33_650M_UR50D"),
        method: str = Query("umap", regex="^(umap|tsne|pca)$"),
        force_recompute: bool = Query(False)
    ):
    with DatabaseContext(orchestrator.db_url) as repo:
        service = GraphService(repo)
        result = service.compute_layout(model_id, method, force_recompute)
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result


@app.get("/v1/proteins")
@track_query_time("get_proteins")
async def get_proteins(
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        search: Optional[str] = Query(None),
        min_confidence: float = Query(0.0, ge=0.0, le=1.0),
        organism: Optional[str] = Query(None),
        include_fallback: bool = Query(True),
        method: str = Query("umap", regex="^(umap|tsne|pca)$"),
        model_id: str = Query("esm2_t33_650M_UR50D")
    ):
    with DatabaseContext(orchestrator.db_url) as repo:
        service = ProteinService(repo)
        return service.get_proteins(
            limit, offset, search, min_confidence,
            organism, include_fallback, method, model_id
        )


@app.on_event("startup")
async def startup_initialization():
    logger.info("HelixStream Gateway starting...")
    
    model_id = "esm2_t33_650M_UR50D" # Remote GPU
    
    try:
        with DatabaseContext(orchestrator.db_url) as repo:
            position_count = repo.check_positions_exist(model_id, 'umap')
            edge_count = repo.check_edges_exist(model_id)
            
            logger.info(f"  Graph positions: {position_count} proteins")
            logger.info(f"  Graph edges: {edge_count} proteins")
            
            if position_count == 0 or edge_count == 0:
                logger.warning("Graph data not initialized. Computing in background...")
                asyncio.create_task(background_graph_initialization(model_id))
            else:
                logger.info("Graph data already initialized")
    except Exception as e:
        logger.error(f"Startup initialization failed: {e}", exc_info=True)
    
    logger.info("Gateway ready on http://localhost:8000")


async def background_graph_initialization(model_id: str):
    try:
        with DatabaseContext(orchestrator.db_url) as repo:
            service = GraphService(repo)
            result = service.initialize_graph_data(model_id)
            
            if "error" in result:
                logger.warning(f"Background initialization: {result['error']}")
            else:
                logger.info(f"Initialized {result['positions']} positions, {result['edges']} edges")
    except Exception as e:
        logger.error(f"Background graph initialization failed: {e}", exc_info=True)

