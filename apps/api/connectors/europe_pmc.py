"""Europe PMC connector (optional, behind toggle)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class EuropePMCConnector(BaseConnector):
    name = "EuropePMC"
    BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
    cache_ttl = 43200  # 12h

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = "%s/search" % self.BASE
        params = {
            "query": query,
            "format": "json",
            "pageSize": min(limit, 25),
            "resultType": "core",
        }
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        results: List[Dict[str, Any]] = []
        for article in data.get("resultList", {}).get("result", []):
            pmid = article.get("pmid", "")
            eid = "PMID:%s" % pmid if pmid else article.get("id", "")
            title = strip_html(article.get("title", ""))
            results.append({
                "id": eid,
                "entity_type": "publication",
                "canonical_name": title,
                "name": title,
                "title": title,
                "authors": [
                    a.get("fullName", "") for a in article.get("authorList", {}).get("author", [])[:5]
                ],
                "journal": article.get("journalTitle", ""),
                "year": int(article.get("pubYear", 0)) if article.get("pubYear") else None,
                "pmid": pmid,
                "doi": article.get("doi", ""),
                "abstract": strip_html(article.get("abstractText", "")),
                "pmc_id": article.get("pmcid", ""),
                "citation_count": article.get("citedByCount"),
                "is_open_access": article.get("isOpenAccess", "N") == "Y",
                "url": "https://europepmc.org/article/MED/%s" % pmid if pmid else "",
                "provenance": [self._prov(
                    url="https://europepmc.org/article/MED/%s" % pmid,
                    ext_id=pmid, confidence=0.95, reasoning="Europe PMC full-text search"
                ).to_dict()],
            })
        return results

    async def fetch_fulltext(self, pmcid: str) -> Optional[str]:
        """Fetch full-text XML from Europe PMC for an open-access paper.

        Uses the Articles RESTful API:
        GET /europepmc/webservices/rest/{source}/{id}/fullTextXML
        Returns plain text extracted from XML, or None if unavailable.
        """
        if not pmcid:
            return None
        url = f"{self.BASE}/PMC/{pmcid}/fullTextXML"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return None
                xml_text = resp.text
                # Extract text from XML body sections
                import xml.etree.ElementTree as ET
                try:
                    root = ET.fromstring(xml_text)
                except ET.ParseError:
                    return xml_text[:10000] if xml_text else None
                # Gather all paragraph text from body
                paragraphs = []
                for elem in root.iter():
                    if elem.tag in ("p", "title", "sec", "abstract"):
                        t = "".join(elem.itertext()).strip()
                        if t and len(t) > 20:
                            paragraphs.append(t)
                return "\n".join(paragraphs) if paragraphs else None
        except Exception:
            return None

    async def count(self, query: str) -> Optional[int]:
        url = "%s/search" % self.BASE
        params = {"query": query, "format": "json", "pageSize": 1}
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return None
        return data.get("hitCount", 0)


