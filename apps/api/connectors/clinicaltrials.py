"""ClinicalTrials.gov v2 connector — using enhanced base."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
from connectors.base import BaseConnector
from core.http_client import ResilientClient


class ClinicalTrialsConnector(BaseConnector):
    name = "ClinicalTrials.gov"
    BASE = "https://clinicaltrials.gov/api/v2"
    cache_ttl = 43200  # 12h

    def __init__(self) -> None:
        super().__init__()
        # ClinicalTrials.gov requires a User-Agent header
        self._client = ResilientClient(timeout=self.http_timeout)
        self._client._client = httpx.AsyncClient(
            timeout=self.http_timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DrugDesigner/1.0",
                "Accept": "application/json",
            },
        )

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = "%s/studies" % self.BASE
        params = {"query.term": query, "pageSize": min(limit, 50), "format": "json"}
        data, meta = await self._cached_get(url, params=params)
        if not data:
            # Fallback: search Europe PMC for clinical trial cross-references
            return await self._epmc_fallback(query, limit)
        results: List[Dict[str, Any]] = []
        for study in data.get("studies", []):
            proto = study.get("protocolSection", {})
            ident = proto.get("identificationModule", {})
            status_mod = proto.get("statusModule", {})
            design = proto.get("designModule", {})
            conds = proto.get("conditionsModule", {})
            arms = proto.get("armsInterventionsModule", {})
            nct_id = ident.get("nctId", "")
            interventions = [i.get("name", "") for i in arms.get("interventions", [])[:5]]
            enrollment_info = proto.get("designModule", {}).get("enrollmentInfo", {})
            results.append({
                "id": nct_id,
                "entity_type": "clinical_trial",
                "canonical_name": ident.get("briefTitle", ""),
                "name": ident.get("briefTitle", ""),
                "nct_id": nct_id,
                "phase": ", ".join(design.get("phases", [])),
                "status": status_mod.get("overallStatus", ""),
                "conditions": conds.get("conditions", []),
                "interventions": interventions,
                "enrollment": enrollment_info.get("count"),
                "url": "https://clinicaltrials.gov/study/%s" % nct_id,
                "provenance": [self._prov(
                    url="https://clinicaltrials.gov/study/%s" % nct_id,
                    ext_id=nct_id, confidence=1.0, reasoning="ClinicalTrials.gov registry"
                ).to_dict()],
            })
        return results

    async def _epmc_fallback(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Fallback: search Europe PMC for clinical trial cross-references."""
        import logging
        logging.getLogger(__name__).warning("ClinicalTrials.gov blocked; using Europe PMC fallback")
        epmc_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": f'"{query}" AND (SRC:CTX OR HAS_CT:y)',
            "resultType": "core",
            "pageSize": min(limit, 25),
            "format": "json",
        }
        data, _ = await self._cached_get(epmc_url, params=params, extra_key="epmc_ct")
        if not data or not isinstance(data, dict):
            return []
        results: List[Dict[str, Any]] = []
        for item in data.get("resultList", {}).get("result", []):
            pmid = item.get("pmid", item.get("id", ""))
            title = item.get("title", "")
            results.append({
                "id": f"EPMC:{pmid}",
                "entity_type": "clinical_trial",
                "canonical_name": title,
                "name": title,
                "nct_id": "",
                "phase": "",
                "status": "published",
                "conditions": [],
                "interventions": [],
                "enrollment": None,
                "url": f"https://europepmc.org/article/MED/{pmid}",
                "source_note": "Via Europe PMC (ClinicalTrials.gov API blocked)",
                "provenance": [self._prov(
                    url=f"https://europepmc.org/article/MED/{pmid}",
                    ext_id=pmid, confidence=0.8, reasoning="Europe PMC clinical trial cross-ref"
                ).to_dict()],
            })
        return results

    async def count(self, query: str) -> Optional[int]:
        url = "%s/studies" % self.BASE
        params = {"query.term": query, "pageSize": 1, "countTotal": "true", "format": "json"}
        data, _ = await self._cached_get(url, params=params, extra_key="count")
        if not data:
            return None
        return data.get("totalCount", 0)

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed trial data by NCT ID."""
        url = f"{self.BASE}/studies/{entity_id}"
        params = {"format": "json"}
        data, meta = await self._cached_get(url, params=params)
        if not data or "protocolSection" not in data:
            return None
        
        proto = data["protocolSection"]
        ident = proto.get("identificationModule", {})
        status_mod = proto.get("statusModule", {})
        design = proto.get("designModule", {})
        conds = proto.get("conditionsModule", {})
        arms = proto.get("armsInterventionsModule", {})
        enrollment_info = design.get("enrollmentInfo", {})
        
        interventions = [i.get("name", "") for i in arms.get("interventions", [])]
        
        return {
            "id": entity_id,
            "entity_type": "clinical_trial",
            "canonical_name": ident.get("briefTitle", ""),
            "name": ident.get("briefTitle", ""),
            "description": ident.get("officialTitle", ""),
            "nct_id": entity_id,
            "phase": ", ".join(design.get("phases", [])),
            "status": status_mod.get("overallStatus", ""),
            "conditions": conds.get("conditions", []),
            "interventions": interventions,
            "enrollment": enrollment_info.get("count"),
            "start_date": status_mod.get("startDateStruct", {}).get("date", ""),
            "completion_date": status_mod.get("completionDateStruct", {}).get("date", ""),
            "sponsor": proto.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", ""),
            "url": f"https://clinicaltrials.gov/study/{entity_id}",
            "provenance": [self._prov(
                url=f"https://clinicaltrials.gov/study/{entity_id}",
                ext_id=entity_id,
                confidence=1.0,
                reasoning="ClinicalTrials.gov detailed trial data"
            ).to_dict()],
        }

    async def search_by_condition(self, condition: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search trials by medical condition."""
        return await self.search(f"AREA[ConditionSearch]{condition}", limit=limit)

    async def search_by_intervention(self, intervention: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search trials by intervention/drug name."""
        return await self.search(f"AREA[InterventionSearch]{intervention}", limit=limit)

    async def search_by_sponsor(self, sponsor: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search trials by sponsor name."""
        return await self.search(f"AREA[LeadSponsorName]{sponsor}", limit=limit)

    async def get_trials_by_phase(self, phase: str, condition: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get trials by phase (e.g., 'Phase 1', 'Phase 2', 'Phase 3', 'Phase 4')."""
        query = f"AREA[Phase]{phase}"
        if condition:
            query += f" AND AREA[ConditionSearch]{condition}"
        return await self.search(query, limit=limit)

    async def get_recruiting_trials(self, condition: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get currently recruiting trials."""
        query = "AREA[OverallStatus]Recruiting"
        if condition:
            query += f" AND AREA[ConditionSearch]{condition}"
        return await self.search(query, limit=limit)

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """Extract evidence records for clinical trial data."""
        trial_data = await self.fetch_by_id(entity_id)
        if not trial_data:
            return []
        
        return [{
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "clinical_trial",
            "confidence": 1.0,
            "phase": trial_data.get("phase"),
            "status": trial_data.get("status"),
            "enrollment": trial_data.get("enrollment"),
            "url": trial_data.get("url"),
            "provenance": self._prov(
                url=trial_data.get("url", ""),
                ext_id=entity_id,
                confidence=1.0,
                reasoning="ClinicalTrials.gov official trial registry"
            ).to_dict()
        }]


