"""PubMed NCBI E-utilities connector — using enhanced base."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class PubMedConnector(BaseConnector):
    name = "PubMed"
    ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    cache_ttl = 21600  # 6h
    http_timeout = 30.0  # 3 sequential API calls need more time

    async def _fetch_abstracts(self, id_list: List[str]) -> Dict[str, str]:
        """Fetch abstracts via efetch XML for a batch of PMIDs."""
        abstracts: Dict[str, str] = {}
        if not id_list:
            return abstracts
        try:
            import xml.etree.ElementTree as ET
            params = {
                "db": "pubmed",
                "id": ",".join(id_list),
                "retmode": "xml",
                "rettype": "abstract",
            }
            data, _ = await self._cached_get(self.EFETCH, params=params, extra_key="abstracts")
            if not data:
                return abstracts
            # data is either XML string (from resp.text fallback) or parsed dict
            xml_text = data if isinstance(data, str) else ""
            if not xml_text:
                return abstracts

            root = ET.fromstring(xml_text)
            for article in root.findall(".//PubmedArticle"):
                pmid_el = article.find(".//PMID")
                # Concatenate all AbstractText elements (structured abstracts)
                abstract_parts = []
                for at in article.findall(".//Abstract/AbstractText"):
                    label = at.get("Label", "")
                    text = (at.text or "").strip()
                    if text:
                        if label:
                            abstract_parts.append(f"{label}: {text}")
                        else:
                            abstract_parts.append(text)
                if pmid_el is not None and abstract_parts:
                    pmid = pmid_el.text or ""
                    if pmid:
                        abstracts[pmid] = strip_html(" ".join(abstract_parts))[:2000]
        except Exception:
            pass
        return abstracts

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        params = {"db": "pubmed", "term": query, "retmax": min(limit, 50), "retmode": "json"}
        data, meta = await self._cached_get(self.ESEARCH, params=params)
        if not data:
            return []
        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []
        summary_params = {"db": "pubmed", "id": ",".join(id_list), "retmode": "json"}
        summary, _ = await self._cached_get(self.ESUMMARY, params=summary_params)
        if not summary:
            return []

        # Fetch abstracts via efetch XML
        abstracts = await self._fetch_abstracts(id_list)

        results: List[Dict[str, Any]] = []
        for pmid in id_list:
            entry = summary.get("result", {}).get(pmid, {})
            if not entry or "error" in entry:
                continue
            authors = [a.get("name", "") for a in entry.get("authors", [])[:5]]
            title = strip_html(entry.get("title", ""))
            abstract = abstracts.get(pmid, "")
            results.append({
                "id": "PMID:%s" % pmid,
                "entity_type": "publication",
                "canonical_name": title,
                "name": title,
                "title": title,
                "authors": authors,
                "journal": entry.get("fulljournalname", ""),
                "year": int(entry.get("pubdate", "0000")[:4]) if entry.get("pubdate") else None,
                "pmid": pmid,
                "doi": entry.get("elocationid", ""),
                "url": "https://pubmed.ncbi.nlm.nih.gov/%s/" % pmid,
                "abstract": abstract,
                "snippet": abstract[:300] if abstract else title,
                "citation_count": 0,
                "provenance": [self._prov(
                    url="https://pubmed.ncbi.nlm.nih.gov/%s/" % pmid,
                    ext_id=pmid, confidence=1.0, reasoning="PubMed indexed"
                ).to_dict()],
            })
        return results

    async def count(self, query: str) -> Optional[int]:
        params = {"db": "pubmed", "term": query, "rettype": "count", "retmode": "json"}
        data, _ = await self._cached_get(self.ESEARCH, params=params, extra_key="count")
        if not data:
            return None
        return int(data.get("esearchresult", {}).get("count", 0))


