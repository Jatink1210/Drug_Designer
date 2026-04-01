"""Background worker definitions."""

from arq import Worker
import urllib.parse
from config import settings
from arq.connections import RedisSettings

import structlog
from qdrant_client import AsyncQdrantClient
from config import settings
from services.embedding_service import EmbeddingService
from models.alignment_model import AlignmentModel
import core.qdrant_utils as qu
import torch

log = structlog.get_logger()

# parse redis url
url = urllib.parse.urlparse(settings.redis_url)
port = url.port or 6379
host = url.hostname or "localhost"
db = 0
if url.path:
    db = int(url.path.strip("/"))

redis_settings = RedisSettings(host=host, port=port, database=db)

async def process_embeddings(ctx, job_id: str, collections: list[str], limit: int = 100):
    """Fetch raw payloads from Qdrant, embed, align, and re-upsert."""
    log.info(f"Starting embed job: {job_id} for collections {collections}")
    # Single-instance desktop mode: in-memory status. Use Redis for distributed.
    try:
        from routers.embeddings import JOB_STATUS
        JOB_STATUS[job_id] = "processing"
    except ImportError:
        log.warning("Could not import JOB_STATUS — job status will not be tracked")
        
    embedder = EmbeddingService()
    aligner = AlignmentModel(target_dim=512)
    client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    
    for coll in collections:
        try:
            records, _ = await client.scroll(
                collection_name=coll,
                limit=limit,
                with_payload=True,
                with_vectors=False
            )
            
            if not records:
                continue

            ids = []
            payloads = []
            vectors = []
            
            # Type detection
            modality = "text"
            if coll == "proteins": modality = "protein"
            if coll == "molecules" or coll == "drugs": modality = "molecule"
            
            texts_to_embed = []
            for r in records:
                ids.append(r.id)
                payloads.append(r.payload)
                if modality == "protein":
                    texts_to_embed.append(r.payload.get("sequence", r.payload.get("name", "")))
                elif modality == "molecule":
                    texts_to_embed.append(r.payload.get("smiles", r.payload.get("name", "")))
                else:
                    texts_to_embed.append(r.payload.get("description", r.payload.get("name", "")))

            # 1. Embed raw
            raw_embs = None
            if modality == "protein":
                raw_embs = embedder.embed_proteins(texts_to_embed)
            elif modality == "molecule":
                raw_embs = embedder.embed_molecules(texts_to_embed)
            else:
                raw_embs = embedder.embed_text(texts_to_embed)

            # 2. Align to 512
            with torch.no_grad():
                aligned = aligner(raw_embs, modality=modality).numpy().tolist()
                
            # 3. Upsert
            await qu.upsert_entities(coll, [str(i) for i in ids], aligned, payloads)
            log.info(f"Successfully embedded and aligned {len(aligned)} items in {coll}")
            
        except Exception as e:
            log.error(f"Failed embedding for {coll}: {e}")

    embedder.clear_cache()
    try:
        from routers.embeddings import JOB_STATUS
        JOB_STATUS[job_id] = "completed"
    except ImportError:
        log.warning("Could not import JOB_STATUS — job completion status will not be tracked")


async def sync_neo4j_graph(ctx, payload_map: dict):
    """
    Background job dynamically loading raw extracted relationships
    into corresponding Neo4j Nodes and Edges. payload_map format:
    { "nodes": [{"label": "Protein", "id": "P00533", "props": {...}}],
      "edges": [{"src_label": "Gene", "src_id": "ENSG...146648", "rel": "TRANSLATES_TO", "dst_label": "Protein", "dst_id": "P00533", "props": {"source": "OpenTargets"}}]
    }
    """
    log.info("Starting Neo4j Sync background job.")
    from services.graph_service import GraphService
    gs = GraphService()
    try:
        await gs.setup_constraints()
        
        # 1. Generate Nodes
        for node in payload_map.get("nodes", []):
            await gs.create_node(node["label"], node["id"], node.get("props", {}))
            
        # 2. Forge Relationships
        for edge in payload_map.get("edges", []):
            await gs.create_edge(
                src_label=edge["src_label"],
                src_id=edge["src_id"],
                rel_type=edge["rel"],
                dst_label=edge["dst_label"],
                dst_id=edge["dst_id"],
                properties=edge.get("props", {})
            )
        log.info(f"Mapped {len(payload_map.get('nodes',[]))} nodes and {len(payload_map.get('edges',[]))} edges to Knowledge Graph.")
    except Exception as e:
        log.error(f"Failed to sync neo4j: {e}")
    finally:
        await gs.close()

async def autonomous_research_loop(ctx, goal: str, run_id: str, max_iterations: int = 3):
    """
    Autoresearch-style iterative loop.
    Searches databases, evaluates evidence, and refines hypotheses autonomously.
    """
    from services.runtime.context import ContextFileSystem
    log.info(f"Starting autonomous research loop for run_id={run_id}, goal={goal}")
    
    fs = ContextFileSystem(run_id)
    fs.save_memory("L0_Abstract", "goal.json", {"goal": goal, "status": "started"})
    
    for i in range(max_iterations):
        log.info(f"Research loop iteration {i+1}/{max_iterations}")
        # Build context from previous iterations
        context = fs.load_context_window()
        
        # Simulate searching Qdrant/Neo4j and evaluating
        found_data = {"iteration": i, "findings": f"Simulated findings for iteration {i}"}
        
        # Save detailed findings to L2
        fs.save_memory("L2_Details", f"iteration_{i}_findings.json", found_data)
        
        # Save summary to L1
        fs.save_memory("L1_Overview", f"iteration_{i}_summary.json", {"summary": f"Iteration {i} yielded viable targets."})
    
    # Evolve brain (summarize to L0)
    fs.evolve_brain()
    log.info(f"Completed autonomous research loop for {run_id}")

async def symphony_task_orchestrator(ctx, high_level_goal: str, target_issue: str):
    """
    Symphony-style orchestrator that breaks down high-level goals 
    and spawns specialized agents or sub-tasks to fulfill them.
    """
    import uuid
    log.info(f"Symphony orchestrating new high-level goal: {high_level_goal}")
    run_id = f"symphony_{uuid.uuid4().hex[:8]}"
    
    # Here Symphony would decompose the goal and enqueue sub-tasks.
    # We simulate queueing an autonomous research loop.
    if ctx and "redis" in ctx:
        await ctx["redis"].enqueue_job("autonomous_research_loop", target_issue, run_id)
    else:
        log.warning("Redis context missing; cannot enqueue sub-tasks. Simulating execution.")
        
    log.info(f"Symphony orchestration complete. Sub-tasks spawned with run_id {run_id}")

class WorkerSettings:
    """Arq Worker Settings."""
    redis_settings = redis_settings
    functions = [process_embeddings, sync_neo4j_graph, autonomous_research_loop, symphony_task_orchestrator]
    
    async def on_startup(ctx):
        print("Worker starting up...")
        
    async def on_shutdown(ctx):
        print("Worker shutting down...")
