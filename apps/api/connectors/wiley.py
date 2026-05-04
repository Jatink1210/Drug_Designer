"""Wiley Online Library connector for scientific literature."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class WileyConnector(BaseConnector):
    """
    Wiley Online Library connector for searching scientific journals and books.
    
    Wiley publishes over 1,600 peer-reviewed journals and thousands of books
    across multiple disciplines including:
    - Life Sciences
    - Health Sciences
    - Physical Sciences & Engineering
    - Social Sciences & Humanities
    
    Note: Requires Wiley API credentials for full access.
    """
    
    name = "Wiley"
    BASE_URL = "https://api.wiley.com/onlinelibrary/tdm/v1/articles"
    cache_ttl = 21600  # 6h
    http_timeout = 20.0
    rate_limit_rps = 3.0  # Conservative rate limit
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search Wiley Online Library for articles.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of article dictionaries
        """
        # Note: Wiley API requires authentication token
        # This implementation provides structure for integration
        
        params = {
            "query": query,
            "pageSize": min(limit, 50),
            "format": "json"
        }
        
        # Add API key from environment if available
        headers = {}
        # headers["Wiley-TDM-Client-Token"] = os.getenv("WILEY_API_KEY", "")
        
        data, meta = await self._cached_get(
            self.BASE_URL,
            params=params,
            headers=headers if headers else None
        )
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        items = data.get("items", []) if isinstance(data, dict) else []
        
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
                
            article_id = item.get("doi", "")
            title = strip_html(item.get("title", ""))
            
            # Parse authors
            authors_data = item.get("authors", [])
            authors = []
            if isinstance(authors_data, list):
                for author in authors_data:
                    if isinstance(author, dict):
                        name = author.get("name", "")
                        if name:
                            authors.append(name)
                    elif isinstance(author, str):
                        authors.append(author)
            
            abstract = strip_html(item.get("abstract", ""))
            
            # Parse publication date
            pub_date = item.get("publicationDate", "")
            year = None
            if pub_date:
                try:
                    year = int(pub_date[:4])
                except (ValueError, TypeError):
                    pass
            
            journal = item.get("publicationTitle", "")
            
            results.append({
                "id": f"Wiley:{article_id}",
                "entity_type": "publication",
                "canonical_name": title,
                "name": title,
                "title": title,
                "authors": authors[:5],
                "journal": journal,
                "year": year,
                "doi": article_id,
                "url": f"https://doi.org/{article_id}" if article_id else "",
                "abstract": abstract,
                "snippet": abstract[:300] if abstract else title,
                "volume": item.get("volume", ""),
                "issue": item.get("issue", ""),
                "pages": item.get("pageRange", ""),
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://doi.org/{article_id}",
                    ext_id=article_id,
                    confidence=0.92,
                    reasoning="Wiley peer-reviewed scientific article"
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
            "query": query,
            "pageSize": 0,
            "format": "json"
        }
        
        data, _ = await self._cached_get(self.BASE_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        return data.get("totalResults", 0)
