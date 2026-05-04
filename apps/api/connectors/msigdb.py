"""MSigDB (Molecular Signatures Database) connector.

Retrieves curated gene sets: hallmark, oncogenic, C2 canonical pathways, etc.
API Reference: https://www.gsea-msigdb.org/gsea/msigdb/
Note: Uses REST API at https://www.gsea-msigdb.org/gsea/msigdb/human/
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class MSigDBConnector(BaseConnector):
    """MSigDB gene set collections via REST API."""

    name = "msigdb"
    BASE_URL = "https://www.gsea-msigdb.org/gsea/msigdb"
    cache_ttl = 86400 * 7  # gene sets are versioned, change slowly

    # Collections: H=hallmark, C1=positional, C2=curated, C3=motif, C4=computational,
    # C5=ontology, C6=oncogenic, C7=immunologic, C8=cell_type
    COLLECTION_MAP = {
        "hallmark": "H",
        "curated": "C2",
        "oncogenic": "C6",
        "immunologic": "C7",
        "go_bp": "C5:GO:BP",
        "go_mf": "C5:GO:MF",
        "go_cc": "C5:GO:CC",
    }

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search gene sets by name/keyword across all collections."""
        data, _meta = await self._cached_get(
            "https://www.gsea-msigdb.org/gsea/msigdb/human/search.jsp",
            params={"keywords": query, "showSelection": False, "submit": "Search"},
            extra_key=query,
        )
        # The MSigDB REST API returns JSON for gene set details
        # Fall back to the geneset search endpoint
        data2, _meta2 = await self._cached_get(
            "https://data.broadinstitute.org/gsea-msigdb/msigdb/release/2023.2.Hs/json/gene_sets.v2023.2.Hs.json",
            extra_key="all_sets_index",
        )
        if not data2 or not isinstance(data2, dict):
            return []
        query_upper = query.upper()
        results = []
        for gs_name, gs_data in data2.items():
            if query_upper in gs_name or (isinstance(gs_data, dict) and query_upper in gs_data.get("description", "").upper()):
                if len(results) >= limit:
                    break
                genes = gs_data.get("geneSymbols", []) if isinstance(gs_data, dict) else []
                results.append({
                    "id": gs_name,
                    "entity_type": "gene_set",
                    "canonical_name": gs_name,
                    "description": gs_data.get("description", "") if isinstance(gs_data, dict) else "",
                    "collection": gs_data.get("collection", "") if isinstance(gs_data, dict) else "",
                    "gene_count": len(genes),
                    "genes": genes[:50],  # First 50 genes for preview
                    "source_db": "MSigDB",
                    "url": f"https://www.gsea-msigdb.org/gsea/msigdb/human/geneset/{gs_name}",
                    "provenance": [self._prov(
                        url=f"https://www.gsea-msigdb.org/gsea/msigdb/human/geneset/{gs_name}",
                        ext_id=gs_name,
                        confidence=0.95,
                        reasoning="MSigDB curated gene set",
                    ).to_dict()],
                })
        return results

    async def fetch_by_id(self, geneset_name: str) -> Optional[Dict[str, Any]]:
        """Fetch a specific gene set by its MSigDB name."""
        data, _meta = await self._cached_get(
            f"https://www.gsea-msigdb.org/gsea/msigdb/human/download_geneset.jsp",
            params={"geneSetName": geneset_name, "fileType": "json"},
            extra_key=geneset_name,
        )
        if not data or not isinstance(data, dict):
            return None
        gs = data.get(geneset_name, {})
        return {
            "id": geneset_name,
            "name": gs.get("exactSource", geneset_name),
            "description": gs.get("description", ""),
            "collection": gs.get("collection", ""),
            "genes": gs.get("geneSymbols", []),
            "gene_count": len(gs.get("geneSymbols", [])),
            "pmid": gs.get("pmid", ""),
            "source_db": "MSigDB",
        }
