"""IGVDB Dataset Loader."""
import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from connectors.base import BaseConnector
from models.entities import VariantEntity, PopulationEvidence, VariantFrequency

log = structlog.get_logger()

class IGVDBLoader(BaseConnector):
    name = "IGVDB"
    data_dir = Path("data/external/indian/igvdb")

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        results = []
        if not self.data_dir.exists():
            log.warning(
                "igvdb.data_dir_missing",
                path=str(self.data_dir),
                hint="Download IGVDB TSV files to this directory to enable Indian population variant search.",
            )
            return results

        
        for file_path in self.data_dir.glob("*.tsv"):
            try:
                with open(file_path, "r") as f:
                    reader = csv.DictReader(f, delimiter="\t")
                    for row in reader:
                        row_lower = {k.lower(): v for k, v in row.items() if k}
                        rsid = row_lower.get("rsid", "")
                        gene = row_lower.get("gene", "")
                        clin_sig = str(row_lower.get("clinical_significance", "")).lower()
                        
                        query_tokens = query.lower().split()
                        match = False
                        for t in query_tokens:
                            if len(t) > 3 and (t in rsid.lower() or t in gene.lower() or t in clin_sig):
                                match = True
                                break
                                
                        if match or query.lower() in rsid.lower() or query.lower() in gene.lower():
                            entity = self.normalize(row_lower)
                            d = entity.model_dump()
                            d["indian_population_relevant"] = True
                            results.append(d)
                            if len(results) >= limit:
                                return results
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
        return results

    def normalize(self, raw_data: Dict[str, Any]) -> VariantEntity:
        rs_id = raw_data.get("rsid", "")
        af_str = raw_data.get("af", "0.0")
        try:
            af = float(af_str)
        except ValueError:
            af = 0.0
            
        freq = VariantFrequency(
            population="IGVDB (India)",
            allele_frequency=af,
            allele_count=int(raw_data["ac"]) if raw_data.get("ac", "").isdigit() else None,
            allele_number=int(raw_data["an"]) if raw_data.get("an", "").isdigit() else None,
            homozygous_count=int(raw_data["hom_count"]) if raw_data.get("hom_count", "").isdigit() else None
        )
        
        evidence = PopulationEvidence(
            dataset_name=self.name,
            frequencies=[freq],
            clinical_significance=raw_data.get("clinical_significance", ""),
            notes="Found in Indian Genetic Variation Database."
        )

        variant = VariantEntity(
            rs_id=rs_id,
            canonical_name=rs_id,
            gene=raw_data.get("gene", ""),
            consequence=raw_data.get("consequence", ""),
            population_evidence=[evidence],
            indian_demographic_context="Variant present in IGVDB cohorts."
        )
        variant.provenance.append(
            self._prov(
                url=f"local://{self.data_dir}", 
                reasoning="Parsed from IGVDB local TSV files."
            ).model_dump()
        )
        return variant
