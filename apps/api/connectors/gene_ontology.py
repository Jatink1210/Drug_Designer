"""Gene Ontology connector via QuickGO API.

Retrieves GO terms, annotations, and gene-GO associations.
API Reference: https://www.ebi.ac.uk/QuickGO/api/index.html
Rate Limits: ~10 req/s, no API key required.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class GeneOntologyConnector(BaseConnector):
    """Query GO terms and annotations via QuickGO REST API."""

    name = "gene_ontology"
    BASE_URL = "https://www.ebi.ac.uk/QuickGO/services"
    cache_ttl = 86400 * 3

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/ontology/go/search",
            params={"query": query, "limit": min(limit, 25), "page": 1},
        )
        if not data or not isinstance(data, dict):
            return []
        results = []
        for result in data.get("results", []):
            go_id = result.get("id", "")
            results.append({
                "id": go_id,
                "entity_type": "go_term",
                "canonical_name": result.get("name", ""),
                "description": result.get("definition", {}).get("text", ""),
                "aspect": result.get("aspect", ""),  # biological_process / molecular_function / cellular_component
                "synonyms": [s.get("name", "") for s in result.get("synonyms", [])],
                "is_obsolete": result.get("isObsolete", False),
                "source_db": "Gene Ontology",
                "url": f"https://www.ebi.ac.uk/QuickGO/term/{go_id}",
                "provenance": [self._prov(
                    url=f"https://www.ebi.ac.uk/QuickGO/term/{go_id}",
                    ext_id=go_id,
                    confidence=1.0,
                    reasoning="Gene Ontology curated term via QuickGO",
                ).to_dict()],
            })
        return results[:limit]

    async def fetch_by_id(self, go_id: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed GO term by GO ID (e.g. GO:0008150)."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/ontology/go/terms/{go_id}"
        )
        if not data or not isinstance(data, dict):
            return None
        results = data.get("results", [])
        if not results:
            return None
        term = results[0]
        return {
            "id": term.get("id", go_id),
            "name": term.get("name", ""),
            "definition": term.get("definition", {}).get("text", ""),
            "aspect": term.get("aspect", ""),
            "synonyms": [s.get("name", "") for s in term.get("synonyms", [])],
            "children": term.get("children", []),
            "xrefs": term.get("xRefs", []),
            "source_db": "Gene Ontology",
        }

    async def get_annotations(self, gene_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get GO annotations for a gene (UniProt ID or gene symbol)."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/annotation/search",
            params={"geneProductId": gene_id, "limit": min(limit, 100)},
        )
        if not data or not isinstance(data, dict):
            return []
        annotations = []
        for ann in data.get("results", [])[:limit]:
            annotations.append({
                "go_id": ann.get("goId", ""),
                "go_name": ann.get("goName", ""),
                "aspect": ann.get("goAspect", ""),
                "evidence_code": ann.get("evidenceCode", ""),
                "reference": ann.get("reference", ""),
                "with_from": ann.get("withFrom", []),
                "assigned_by": ann.get("assignedBy", ""),
                "source_db": "Gene Ontology",
            })
        return annotations
