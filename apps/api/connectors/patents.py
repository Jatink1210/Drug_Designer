"""Patent connector — via Europe PMC patent literature (free, no API key).

Original PatentsView API was permanently deprecated (410 Gone).
This connector uses Europe PMC's patent source filter (SRC:PAT) which
indexes patents from USPTO, EPO, and WIPO with biomedical relevance.
API: https://europepmc.org/RestfulWebService
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class PatentsViewConnector(BaseConnector):
    name = "PatentsView"
    BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    cache_ttl = 172800  # 48h

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        params = {
            "query": f"SRC:PAT AND {query}",
            "format": "json",
            "pageSize": min(limit, 25),
            "resultType": "core",
        }
        data, meta = await self._cached_get(self.BASE, params=params)
        if not data or not isinstance(data, dict):
            return []
        results: List[Dict[str, Any]] = []
        for pat in data.get("resultList", {}).get("result", []):
            pat_id = pat.get("id", "")
            source = pat.get("source", "PAT")
            title = pat.get("title", "")
            abstract = (pat.get("abstractText", "") or "")[:500]
            authors = pat.get("authorString", "")
            pub_date = pat.get("firstPublicationDate", "")
            results.append({
                "id": f"PAT:{pat_id}",
                "entity_type": "patent",
                "canonical_name": title,
                "name": title,
                "title": title,
                "patent_id": pat_id,
                "abstract": abstract,
                "filing_date": pub_date,
                "assignee": authors,
                "source_db": f"Europe PMC ({source})",
                "url": f"https://europepmc.org/article/{source}/{pat_id}",
                "provenance": [self._prov(
                    url=f"https://europepmc.org/article/{source}/{pat_id}",
                    ext_id=pat_id, confidence=0.9,
                    reasoning="Europe PMC patent search (PatentsView alt)"
                ).to_dict()],
            })
        return results


