"""DrugBank connector — with PubChem fallback for drug data.

DrugBank website is Cloudflare-protected. When HTML scraping fails,
this connector falls back to PubChem's free compound search.
"""

from __future__ import annotations
import logging
import re
from typing import Any, Dict, List
from .base import BaseConnector

log = logging.getLogger(__name__)


class DrugBankConnector(BaseConnector):
    """Search DrugBank Open Data for drugs and their targets.
    
    Uses the free DrugBank Open Data vocabulary queries.
    Full DrugBank API requires academic/commercial license.
    HTML responses are parsed into structured items.
    """

    name = "drugbank"
    BASE_URL = "https://go.drugbank.com/unearth/q"

    def _parse_html_results(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Extract drug entries from DrugBank HTML search results."""
        items: List[Dict[str, Any]] = []
        drug_pattern = re.compile(
            r'<a\s+href="/drugs/(DB\d+)"[^>]*>\s*(.+?)\s*</a>',
            re.IGNORECASE,
        )
        for match in drug_pattern.finditer(html):
            db_id = match.group(1)
            name = re.sub(r"<[^>]+>", "", match.group(2)).strip()
            if not name or db_id in {item.get("external_id") for item in items}:
                continue
            items.append({
                "external_id": db_id,
                "title": name,
                "url": f"https://go.drugbank.com/drugs/{db_id}",
                "source": "drugbank",
            })
            if len(items) >= limit:
                break
        return items

    async def _pubchem_fallback(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Fallback: search PubChem for compound data when DrugBank is blocked."""
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{query}/JSON"
        body, meta = await self._cached_get(url, extra_key="pubchem_fallback")
        if not body or not isinstance(body, dict):
            return []
        compounds = body.get("PC_Compounds", [])
        results: List[Dict[str, Any]] = []
        for cpd in compounds[:limit]:
            cid = str(cpd.get("id", {}).get("id", {}).get("cid", ""))
            props = {p.get("urn", {}).get("label", ""): p.get("value", {}) for p in cpd.get("props", [])}
            name = props.get("IUPAC Name", {}).get("sval", query)
            results.append({
                "id": f"DrugBank:PubChem:{cid}",
                "entity_type": "drug",
                "canonical_name": name if isinstance(name, str) else query,
                "name": query,
                "cid": cid,
                "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
                "source_db": "DrugBank (via PubChem)",
                "provenance": [self._prov(
                    url=f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
                    ext_id=cid, confidence=0.7,
                    reasoning="PubChem fallback (DrugBank blocked)"
                ).to_dict()],
            })
        return results

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = self.BASE_URL
        params = {
            "searcher": "drugs",
            "query": query,
            "approved": "1",
            "button": "",
        }
        body, meta = await self._cached_get(url, params=params, extra_key=f"limit={limit}")
        
        if body is None:
            log.info("DrugBank unavailable, falling back to PubChem")
            return await self._pubchem_fallback(query, limit)

        # If body is a string (HTML response), parse it
        if isinstance(body, str):
            items = self._parse_html_results(body, limit)
            if items:
                return [
                    {
                        "id": f"DrugBank:{it['external_id']}",
                        "entity_type": "drug",
                        "canonical_name": it["title"],
                        "name": it["title"],
                        "url": it["url"],
                        "source_db": "DrugBank",
                        "provenance": [self._prov(
                            url=it["url"], ext_id=it["external_id"],
                            confidence=0.8, reasoning="DrugBank HTML parsed"
                        ).to_dict()],
                    }
                    for it in items
                ]
            # HTML but no drug results — try PubChem
            return await self._pubchem_fallback(query, limit)

        # If API returns JSON (licensed access)
        if isinstance(body, dict):
            drugs = body.get("drugs", body.get("results", [body]))
            return [
                {
                    "id": f"DrugBank:{d.get('drugbank_id', '')}",
                    "entity_type": "drug",
                    "canonical_name": d.get("name", ""),
                    "name": d.get("name", ""),
                    "source_db": "DrugBank",
                }
                for d in (drugs if isinstance(drugs, list) else [drugs])
            ][:limit]

        return []

    async def fetch_by_id(self, entity_id: str) -> Dict[str, Any] | None:
        url = f"https://go.drugbank.com/drugs/{entity_id}.json"
        body, meta = await self._cached_get(url)
        if body and isinstance(body, dict):
            return body
        # Fallback: try HTML page and extract basic info
        html_url = f"https://go.drugbank.com/drugs/{entity_id}"
        body, meta = await self._cached_get(html_url)
        if isinstance(body, str):
            title_match = re.search(r"<title>(.+?)</title>", body, re.IGNORECASE)
            name = title_match.group(1).split(" - ")[0].strip() if title_match else entity_id
            return {
                "external_id": entity_id,
                "title": name,
                "url": html_url,
                "source": "drugbank",
            }
        return None
