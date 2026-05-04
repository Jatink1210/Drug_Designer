"""PLoS (Public Library of Science) connector for open-access scientific literature."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class PLoSConnector(BaseConnector):
    """
    PLoS connector for searching open-access scientific journals.
    
    PLoS publishes peer-reviewed open-access journals including:
    - PLoS ONE
    - PLoS Biology
    - PLoS Medicine
    - PLoS Computational Biology
    - PLoS Genetics
    - PLoS Pathogens
    - PLoS Neglected Tropical Diseases
    """
    
    name = "PLoS"
    BASE_URL = "https://api.plos.org/search"
    cache_ttl = 21600  # 6h
    http_timeout = 20.0
    rate_limit_rps = 5.0  # PLoS allows reasonable rate limits
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search PLoS for open-access articles.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of article dictionaries
        """
        params = {
            "q": query,
            "rows": min(limit, 100),
            "wt": "json",
            "fl": "id,title,author,journal,publication_date,abstract,doi,article_type"
        }
        
        data, meta = await self._cached_get(self.BASE_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        response = data.get("response", {})
        docs = response.get("docs", []) if isinstance(response, dict) else []
        
        for doc in docs[:limit]:
            if not isinstance(doc, dict):
                continue
                
            article_id = doc.get("id", "")
            title = strip_html(doc.get("title", [""])[0] if isinstance(doc.get("title"), list) else doc.get("title", ""))
            
            # Parse authors
            authors = doc.get("author", [])
            if isinstance(authors, str):
                authors = [authors]
            
            # Parse abstract
            abstract_list = doc.get("abstract", [])
            abstract = strip_html(abstract_list[0] if isinstance(abstract_list, list) and abstract_list else "")
            
            # Parse publication date
            pub_date = doc.get("publication_date", "")
            year = None
            if pub_date:
                try:
                    year = int(pub_date[:4])
                except (ValueError, TypeError):
                    pass
            
            doi = doc.get("doi", "")
            journal = doc.get("journal", "")
            
            results.append({
                "id": f"PLoS:{article_id}",
                "entity_type": "publication",
                "canonical_name": title,
                "name": title,
                "title": title,
                "authors": authors[:5] if isinstance(authors, list) else [],
                "journal": journal,
                "year": year,
                "doi": doi,
                "url": f"https://journals.plos.org/plosone/article?id={doi}" if doi else "",
                "abstract": abstract,
                "snippet": abstract[:300] if abstract else title,
                "article_type": doc.get("article_type", ""),
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://journals.plos.org/plosone/article?id={doi}",
                    ext_id=article_id,
                    confidence=0.95,
                    reasoning="PLoS peer-reviewed open-access article"
                ).to_dict()],
            })
        
        return results
    
    async def count(self, query: str) -> Optional[int]:
        """
        Get count of search results.
        
        Args:
            query: Search query string
            
        Returns:
            Number of results or None
        """
        params = {
            "q": query,
            "rows": 0,
            "wt": "json"
        }
        
        data, _ = await self._cached_get(self.BASE_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        response = data.get("response", {})
        return response.get("numFound", 0) if isinstance(response, dict) else None
