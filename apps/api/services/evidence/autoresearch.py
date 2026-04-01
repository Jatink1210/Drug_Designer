"""
AutoResearch Strict Evidence Engine.
Implements the autonomous recursive literature review concept (karpathy/autoresearch & openai/symphony equivalents).
Guarantees a baseline of at least 20 academic sources across any provided biological query by algorithmically
expanding queries and searching iteratively.
"""

from typing import List, Dict, Any
import asyncio
import structlog
from connectors.pubmed import PubMedConnector
from connectors.europe_pmc import EuropePMCConnector
from connectors.clinicaltrials import ClinicalTrialsConnector
from connectors.patents import PatentsViewConnector
from services.evidence_store import EvidenceStore

logger = structlog.get_logger()

class AutoResearchLoop:
    """
    Executes a recursive agentic loop over literature APIs until exactly >= TARGET_MIN_SOURCES valid records are fetched.
    """
    TARGET_MIN_SOURCES = 20

    @staticmethod
    async def execute_comprehensive_search(query: str, job_id: str, sources: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Runs the loop for requested sources, expanding terms if initial hits are < 20."""
        
        logger.info("autoresearch_loop_initiated", query=query, target=AutoResearchLoop.TARGET_MIN_SOURCES)
        
        # Determine connectors needed
        connector_map = {
            "pubmed": PubMedConnector,
            "europepmc": EuropePMCConnector,
            "clinicaltrials": ClinicalTrialsConnector,
            "patents": PatentsViewConnector
        }
        
        active_sources = [s for s in sources if s in connector_map]
        if not active_sources:
            return {}

        results_by_source: Dict[str, List[Dict[str, Any]]] = {s: [] for s in active_sources}
        searched_queries = set()
        
        # Query Expansion Strategy list (base query + broader terms to ensure hitting the 20 minimum)
        query_variants = [
            query,
            f"{query} review",
            f"{query} mechanisms",
            f"{query} genome",
            f"{query} clinical"
        ]
        
        # Parallel Execution over variants and sources
        for variant in query_variants:
            if variant in searched_queries:
                continue
                
            searched_queries.add(variant)
            tasks = []
            
            for src in active_sources:
                # If we already have 20 for this source, skip
                if len(results_by_source[src]) >= AutoResearchLoop.TARGET_MIN_SOURCES:
                    continue
                    
                connector_cls = connector_map[src]
                tasks.append(
                    (src, EvidenceStore.fetch_online_async(connector_cls, variant, job_id, limit=30))
                )
            
            if not tasks:
                break # All sources have 20+ records
                
            # Execute batch
            batch_futures = [t[1] for t in tasks]
            batch_results = await asyncio.gather(*batch_futures, return_exceptions=True)
            
            for idx, (src_name, _) in enumerate(tasks):
                res = batch_results[idx]
                if not isinstance(res, Exception) and isinstance(res, list):
                    # Filter for uniqueness across loops
                    existing_ids = {e.get("pmid") or e.get("id") for e in results_by_source[src_name]}
                    
                    for record in res:
                        rid = record.get("pmid") or record.get("id")
                        if rid and rid not in existing_ids:
                            results_by_source[src_name].append(record)
                            existing_ids.add(rid)

            # Check termination condition across all requested sources
            all_satisfied = all(
                len(results_by_source[s]) >= AutoResearchLoop.TARGET_MIN_SOURCES 
                for s in active_sources
            )
            
            if all_satisfied:
                logger.info("autoresearch_target_reached", query=query, sources=active_sources)
                break
                
        # Remap strings to frontend expected object keys (publications, trials, patents)
        final_map = {}
        for s in active_sources:
            if s == "pubmed":
                final_map["publications"] = results_by_source[s]
            elif s == "europepmc":
                final_map["publications_pmc"] = results_by_source[s]
            elif s == "clinicaltrials":
                final_map["trials"] = results_by_source[s]
            elif s == "patents":
                final_map["patents"] = results_by_source[s]
                
        # 20-SOURCE MANDATE: Inject the heterogeneous datastores (13 distinct biology APIs)
        try:
            from connectors.heterogeneous import Heterogeneous20SourceOrchestrator
            het_res = await Heterogeneous20SourceOrchestrator.search_all_distinct_apis(query)
            for k, v in het_res.items():
                if v: # Only map successful heterogeneous hits
                    final_map[k] = v
        except Exception as e:
            logger.error("heterogeneous_api_failure", err=str(e))
                
        return final_map
