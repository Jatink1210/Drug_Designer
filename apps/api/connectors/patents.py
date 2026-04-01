"""PatentsView connector (optional, behind toggle)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class PatentsViewConnector(BaseConnector):
    name = "PatentsView"
    BASE = "https://api.patentsview.org/patents/query"
    cache_ttl = 172800  # 48h

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        body = {
            "q": {"_text_any": {"patent_abstract": query}},
            "f": [
                "patent_number", "patent_title", "patent_abstract",
                "patent_date", "assignee_organization",
            ],
            "o": {"per_page": min(limit, 25)},
        }
        data, meta = await self._cached_post(self.BASE, json_body=body)
        if not data:
            return []
        results: List[Dict[str, Any]] = []
        for pat in data.get("patents", []):
            pnum = pat.get("patent_number", "")
            assignees = pat.get("assignees", [])
            org = assignees[0].get("assignee_organization", "") if assignees else ""
            results.append({
                "id": "PAT:%s" % pnum,
                "entity_type": "patent",
                "canonical_name": pat.get("patent_title", ""),
                "name": pat.get("patent_title", ""),
                "title": pat.get("patent_title", ""),
                "patent_id": pnum,
                "abstract": (pat.get("patent_abstract", "") or "")[:500],
                "filing_date": pat.get("patent_date", ""),
                "assignee": org,
                "url": "https://patents.google.com/patent/US%s" % pnum,
                "provenance": [self._prov(
                    url="https://patents.google.com/patent/US%s" % pnum,
                    ext_id=pnum, confidence=0.9, reasoning="PatentsView API"
                ).to_dict()],
            })
        return results


