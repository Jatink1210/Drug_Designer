"""KEGG Drug connector for drug information from KEGG database."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class KEGGDrugConnector(BaseConnector):
    """
    KEGG Drug connector for comprehensive drug information.
    
    KEGG DRUG is a comprehensive drug information resource for approved
    drugs in Japan, USA, and Europe, unified based on the chemical
    structures and/or the chemical components.
    
    Provides:
    - Drug structures
    - Drug targets
    - Drug metabolism
    - Drug interactions
    - Therapeutic categories
    - Chemical structures
    
    Integrates with KEGG PATHWAY, KEGG BRITE, and other KEGG databases.
    """
    
    name = "KEGG Drug"
    BASE_URL = "https://rest.kegg.jp"
    SEARCH_URL = "https://rest.kegg.jp/find/drug"
    cache_ttl = 86400  # 24h (drug data changes infrequently)
    http_timeout = 20.0
    rate_limit_rps = 5.0  # KEGG has rate limits
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search KEGG Drug for drugs.
        
        Args:
            query: Search query string (drug name)
            limit: Maximum number of results
            
        Returns:
            List of drug dictionaries
        """
        url = f"{self.SEARCH_URL}/{query}"
        
        data, meta = await self._cached_get(url)
        
        if not data or not isinstance(data, str):
            return []
        
        results: List[Dict[str, Any]] = []
        
        # KEGG returns tab-separated text format
        lines = data.strip().split('\n')
        
        for line in lines[:limit]:
            if not line.strip():
                continue
                
            parts = line.split('\t')
            if len(parts) < 2:
                continue
                
            drug_id = parts[0].strip()
            description = parts[1].strip()
            
            # Extract drug name (before semicolon)
            name = description.split(';')[0].strip()
            
            results.append({
                "id": f"KEGG:{drug_id}",
                "entity_type": "drug",
                "canonical_name": name,
                "name": name,
                "kegg_id": drug_id,
                "description": description,
                "url": f"https://www.kegg.jp/entry/{drug_id}",
                "snippet": description[:300],
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://www.kegg.jp/entry/{drug_id}",
                    ext_id=drug_id,
                    confidence=0.97,
                    reasoning="KEGG Drug database entry"
                ).to_dict()],
            })
        
        return results
    
    async def get_drug_details(self, drug_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific drug.
        
        Args:
            drug_id: KEGG drug ID (e.g., D00001)
            
        Returns:
            Detailed drug information or None
        """
        url = f"{self.BASE_URL}/get/{drug_id}"
        
        data, meta = await self._cached_get(url)
        
        if not data or not isinstance(data, str):
            return None
        
        # Parse KEGG flat file format
        details = {
            "drug_id": drug_id,
            "name": "",
            "formula": "",
            "targets": [],
            "pathways": []
        }
        
        current_field = None
        for line in data.split('\n'):
            if line.startswith('NAME'):
                details["name"] = line.split('NAME')[1].strip()
            elif line.startswith('FORMULA'):
                details["formula"] = line.split('FORMULA')[1].strip()
            elif line.startswith('TARGET'):
                current_field = "targets"
            elif line.startswith('PATHWAY'):
                current_field = "pathways"
            elif current_field and line.startswith(' '):
                if current_field == "targets":
                    details["targets"].append(line.strip())
                elif current_field == "pathways":
                    details["pathways"].append(line.strip())
        
        return details
    
    async def count(self, query: str) -> Optional[int]:
        """
        Get count of search results.
        
        Args:
            query: Search query string
            
        Returns:
            Number of results or None
        """
        # KEGG doesn't provide count, need to fetch and count
        url = f"{self.SEARCH_URL}/{query}"
        
        data, _ = await self._cached_get(url, extra_key="count")
        
        if not data or not isinstance(data, str):
            return None
        
        lines = [l for l in data.strip().split('\n') if l.strip()]
        return len(lines)
