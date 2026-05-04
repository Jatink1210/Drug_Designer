"""Nature Portfolio connector for scientific literature."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class NatureConnector(BaseConnector):
    """
    Nature Portfolio connector for searching scientific journals.
    
    Nature Portfolio publishes high-impact journals including:
    - Nature
    - Nature Medicine
    - Nature Biotechnology
    - Nature Genetics
    - Nature Chemistry
    - Nature Communications
    - Scientific Reports
    - And 50+ other specialized journals
    
    Note: Requires Nature API credentials for full access.
    """
    
    name = "Nature"
    BASE_URL = "https://api.springernature.com/meta/v2/json"
    cache_ttl = 21600  # 6h
    http_timeout = 20.0
    rate_limit_rps = 3.0  # Conservative rate limit
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search Nature Portfolio for articles.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of article dictionaries
        """
        # Note: Nature API requires API key
        # This implementation provides structure for integration
        
        params = {
            "q": f'pub:Nature* AND ({query})',  # Filter to Nature journals
            "p": min(limit, 50),
            "s": 1,  # Start position
            # "api_key": os.getenv("NATURE_API_KEY", "")
        }
        
        data, meta = await self._cached_get(self.BASE_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        records = data.get("records", []) if isinstance(data, dict) else []
        
        for record in records[:limit]:
            if not isinstance(record, dict):
                continue
                
            # Parse DOI
            identifiers = record.get("identifier", [])
            doi = ""
            if isinstance(identifiers, list):
                for identifier in identifiers:
                    if isinstance(identifier, dict) and identifier.get("type") == "doi":
                        doi = identifier.get("value", "")
                        break
            
            article_id = doi or record.get("url", "")
            title = strip_html(record.get("title", ""))
            
            # Parse authors
            creators = record.get("creators", [])
            authors = []
            if isinstance(creators, list):
                for creator in creators:
                    if isinstance(creator, dict):
                        name = creator.get("creator", "")
                        if name:
                            authors.append(name)
                    elif isinstance(creator, str):
                        authors.append(creator)
            
            abstract = strip_html(record.get("abstract", ""))
            
            # Parse publication date
            pub_date = record.get("publicationDate", "")
            year = None
            if pub_date:
                try:
                    year = int(pub_date[:4])
                except (ValueError, TypeError):
                    pass
            
            journal = record.get("publicationName", "")
            
            results.append({
                "id": f"Nature:{doi or article_id}",
                "entity_type": "publication",
                "canonical_name": title,
                "name": title,
                "title": title,
                "authors": authors[:5],
                "journal": journal,
                "year": year,
                "doi": doi,
                "url": record.get("url", f"https://doi.org/{doi}" if doi else ""),
                "abstract": abstract,
                "snippet": abstract[:300] if abstract else title,
                "volume": record.get("volume", ""),
                "issue": record.get("number", ""),
                "pages": record.get("startingPage", ""),
                "article_type": record.get("contentType", ""),
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://doi.org/{doi}" if doi else record.get("url", ""),
                    ext_id=doi or article_id,
                    confidence=0.95,
                    reasoning="Nature Portfolio high-impact peer-reviewed article"
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
            "q": f'pub:Nature* AND ({query})',
            "p": 0,
            "s": 1
        }
        
        data, _ = await self._cached_get(self.BASE_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        return data.get("total", 0)
