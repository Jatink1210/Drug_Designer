"""KEGG (Kyoto Encyclopedia of Genes and Genomes) connector."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from .base import BaseConnector
import structlog

log = structlog.get_logger(__name__)


class KEGGConnector(BaseConnector):
    """Query KEGG REST API for pathways, compounds, and diseases."""

    name = "kegg"
    BASE_URL = "https://rest.kegg.jp"

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        # Strategy 1: Direct pathway name search
        url = f"{self.BASE_URL}/find/pathway/{query}"
        body, meta = await self._cached_get(url)
        if body:
            text = body if isinstance(body, str) else str(body)
            for line in text.strip().split("\n")[:limit]:
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    pid = parts[0].strip()
                    raw_name = parts[1].strip()
                    if " - Homo sapiens" in raw_name:
                        raw_name = raw_name[:raw_name.index(" - Homo sapiens")].strip()
                    results.append({
                        "id": pid,
                        "entity_type": "pathway",
                        "canonical_name": raw_name,
                        "name": raw_name,
                        "description": "",
                        "pathway_id": pid,
                        "source_db": "KEGG",
                        "species": "Homo sapiens",
                        "url": f"https://www.kegg.jp/entry/{pid}",
                        "provenance": [self._prov(
                            url=f"https://www.kegg.jp/entry/{pid}",
                            ext_id=pid, confidence=0.90, reasoning="KEGG curated pathway"
                        ).to_dict()],
                    })

        # Strategy 2: If few results, try gene-to-pathway lookup via human gene link
        if len(results) < 3:
            gene_query = query.strip().upper()
            try:
                # Find KEGG gene ID from gene symbol
                find_url = f"{self.BASE_URL}/find/genes/{gene_query.lower()}"
                gene_body, _ = await self._cached_get(find_url)
                kegg_gene_id = None
                if gene_body:
                    gene_text = gene_body if isinstance(gene_body, str) else str(gene_body)
                    # Look for exact gene symbol match in human (hsa:) entries
                    for line in gene_text.strip().split("\n"):
                        if not line.startswith("hsa:"):
                            continue
                        parts = line.split("\t", 1)
                        if len(parts) == 2:
                            desc = parts[1]
                            # Check if the gene symbol exactly matches
                            symbols = [s.strip().upper() for s in desc.split(";")[0].split(",")]
                            if gene_query in symbols:
                                kegg_gene_id = parts[0].strip()
                                break
                    # Fallback: first hsa: entry
                    if not kegg_gene_id:
                        for line in gene_text.strip().split("\n"):
                            if line.startswith("hsa:"):
                                kegg_gene_id = line.split("\t")[0].strip()
                                break

                if kegg_gene_id:
                    # Get pathways linked to this gene
                    link_url = f"{self.BASE_URL}/link/pathway/{kegg_gene_id}"
                    link_body, _ = await self._cached_get(link_url)
                    if link_body:
                        link_text = link_body if isinstance(link_body, str) else str(link_body)
                        existing_ids = {r["id"] for r in results}
                        pathway_ids = []
                        for line in link_text.strip().split("\n"):
                            parts = line.split("\t")
                            if len(parts) >= 2:
                                pid = parts[1].strip().replace("path:", "")
                                if pid not in existing_ids:
                                    pathway_ids.append(pid)

                        # Fetch names for discovered pathways
                        for pid in pathway_ids[:limit - len(results)]:
                            try:
                                info_url = f"{self.BASE_URL}/get/{pid}"
                                info_body, _ = await self._cached_get(info_url)
                                name = pid
                                if info_body:
                                    info_text = info_body if isinstance(info_body, str) else str(info_body)
                                    for iline in info_text.split("\n"):
                                        if iline.startswith("NAME"):
                                            raw_name = iline[4:].strip()
                                            # Remove species suffix
                                            if " - Homo sapiens" in raw_name:
                                                name = raw_name[:raw_name.index(" - Homo sapiens")].strip()
                                            else:
                                                name = raw_name
                                            break
                                results.append({
                                    "id": pid,
                                    "entity_type": "pathway",
                                    "canonical_name": name,
                                    "name": name,
                                    "description": "",
                                    "pathway_id": pid,
                                    "source_db": "KEGG",
                                    "species": "Homo sapiens",
                                    "url": f"https://www.kegg.jp/entry/{pid}",
                                    "linked_gene": gene_query,
                                    "provenance": [self._prov(
                                        url=f"https://www.kegg.jp/entry/{pid}",
                                        ext_id=pid, confidence=0.90, reasoning="KEGG curated pathway"
                                    ).to_dict()],
                                })
                            except Exception:
                                results.append({
                                    "id": pid,
                                    "entity_type": "pathway",
                                    "canonical_name": pid,
                                    "name": pid,
                                    "description": "",
                                    "pathway_id": pid,
                                    "source_db": "KEGG",
                                    "species": "Homo sapiens",
                                    "url": f"https://www.kegg.jp/entry/{pid}",
                                    "linked_gene": gene_query,
                                })
            except Exception as e:
                log.warning("kegg_gene_pathway_lookup_failed", query=query, error=str(e))

        return results[:limit]

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}/get/{entity_id}"
        body, meta = await self._cached_get(url)
        if not body:
            return None

        text = body if isinstance(body, str) else str(body)

        # Parse KEGG flat file for NAME, DESCRIPTION, and GENE section
        name = entity_id
        description = ""
        genes: list[str] = []
        in_gene_section = False

        for line in text.split("\n"):
            if line.startswith("NAME"):
                raw = line[12:].strip()
                if " - Homo sapiens" in raw:
                    name = raw[:raw.index(" - Homo sapiens")].strip()
                else:
                    name = raw
            elif line.startswith("DESCRIPTION"):
                description = line[12:].strip()
            elif line.startswith("GENE"):
                in_gene_section = True
                # First gene on same line as GENE header
                parts = line[12:].strip().split(None, 1)
                if len(parts) >= 2:
                    # Format: "7157  TP53; tumor protein p53 [KO:K04451]"
                    gene_desc = parts[1]
                    gene_sym = gene_desc.split(";")[0].strip()
                    if gene_sym:
                        genes.append(gene_sym)
                elif parts:
                    genes.append(parts[0].strip())
            elif in_gene_section and line.startswith("            "):
                # Continuation of GENE section (12-space indent)
                parts = line.strip().split(None, 1)
                if len(parts) >= 2:
                    gene_desc = parts[1]
                    gene_sym = gene_desc.split(";")[0].strip()
                    if gene_sym:
                        genes.append(gene_sym)
                elif parts:
                    genes.append(parts[0].strip())
            elif in_gene_section and not line.startswith(" "):
                in_gene_section = False

        return {
            "id": entity_id,
            "entity_type": "pathway",
            "canonical_name": name,
            "pathway_id": entity_id,
            "source_db": "KEGG",
            "genes": genes[:200],
            "gene_count": len(genes),
            "description": description,
            "url": f"https://www.kegg.jp/entry/{entity_id}",
        }

    async def count(self, query: str) -> Optional[int]:
        results = await self.search(query, limit=1000)
        return len(results)
