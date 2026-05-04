"""OpenAlex connector — free, no API key needed.

Covers: 250M+ scholarly works, authors, institutions, concepts.
API Reference: https://docs.openalex.org/
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector, strip_html


class OpenAlexConnector(BaseConnector):
    name = "OpenAlex"
    BASE_URL = "https://api.openalex.org"
    cache_ttl = 21600

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        params = {
            "search": query,
            "per_page": min(limit, 50),
            "select": "id,doi,title,publication_year,cited_by_count,authorships,primary_location,abstract_inverted_index",
        }
        data, meta = await self._cached_get(f"{self.BASE_URL}/works", params=params)
        if not data or "results" not in data:
            return []
        results = []
        for work in data["results"]:
            authors = [
                a.get("author", {}).get("display_name", "")
                for a in (work.get("authorships") or [])[:5]
            ]
            loc = work.get("primary_location") or {}
            journal = (loc.get("source") or {}).get("display_name", "")
            # Reconstruct abstract from inverted index
            abstract = ""
            aii = work.get("abstract_inverted_index")
            if aii and isinstance(aii, dict):
                positions: dict[int, str] = {}
                for word, pos_list in aii.items():
                    for pos in pos_list:
                        positions[pos] = word
                if positions:
                    abstract = " ".join(positions[k] for k in sorted(positions))[:500]
            title = strip_html(work.get("title", ""))
            results.append({
                "id": work.get("id", ""),
                "entity_type": "publication",
                "canonical_name": title,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "journal": journal,
                "year": work.get("publication_year"),
                "doi": (work.get("doi") or "").replace("https://doi.org/", ""),
                "url": work.get("id", ""),
                "citation_count": work.get("cited_by_count", 0),
                "provenance": [self._prov(
                    url=work.get("id", ""), confidence=1.0, reasoning="OpenAlex indexed"
                ).to_dict()],
            })
        return results

    async def count(self, query: str) -> Optional[int]:
        data, _ = await self._cached_get(
            f"{self.BASE_URL}/works", params={"search": query, "per_page": 1}, extra_key="count"
        )
        if not data:
            return None
        return data.get("meta", {}).get("count", 0)
