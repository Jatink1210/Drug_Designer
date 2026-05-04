"""JSTOR connector for academic literature search."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class JSTORConnector(BaseConnector):
    """
    JSTOR connector for searching academic journals and articles.
    
    Note: JSTOR requires API access credentials. This implementation
    provides a basic structure that can be extended with proper API keys.
    """
    
    name = "JSTOR"
    BASE_URL = "https://www.jstor.org/api/search"
    cache_ttl = 21600  # 6h
    http_timeout = 20.0
    rate_limit_rps = 2.0  # Conservative rate limit
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search JSTOR for academic articles.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of article dictionaries
        """
        # Note: JSTOR API requires authentication
        # This is a placeholder implementation that would need proper API credentials
        
        params = {
            "q": query,
            "limit": min(limit, 50),
            "format": "json"
        }
        
        data, meta = await self._cached_get(self.BASE_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        items = data.get("items", []) if isinstance(data, dict) else []
        
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
                
            article_id = item.get("id", "")
            title = strip_html(item.get("title", ""))
            authors = item.get("authors", [])
            if isinstance(authors, str):
                authors = [authors]
            
            abstract = strip_html(item.get("abstract", ""))
            
            results.append({
                "id": f"JSTOR:{article_id}",
                "entity_type": "publication",
                "canonical_name": title,
                "name": title,
                "title": title,
                "authors": authors[:5] if isinstance(authors, list) else [],
                "journal": item.get("journal", ""),
                "year": item.get("year"),
                "doi": item.get("doi", ""),
                "url": f"https://www.jstor.org/stable/{article_id}" if article_id else "",
                "abstract": abstract,
                "snippet": abstract[:300] if abstract else title,
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://www.jstor.org/stable/{article_id}",
                    ext_id=article_id,
                    confidence=0.9,
                    reasoning="JSTOR indexed academic article"
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
            "limit": 0,
            "format": "json"
        }
        
        data, _ = await self._cached_get(self.BASE_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        return data.get("total", 0)
