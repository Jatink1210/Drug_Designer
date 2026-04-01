"""GWAS Catalog API Connector."""
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector
from models.entities import VariantEntity

class GWASCatalogConnector(BaseConnector):
    name = "GWASCatalog"
    base_url = "https://www.ebi.ac.uk/gwas/rest/api"

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        # Naive lookup for a variant by rsID
        url = f"{self.base_url}/singleNucleotidePolymorphisms/{query}"
        data, meta = await self._cached_get(url)
        results = []
        if data and not data.get("error"):
            # Fetch associations for this SNP for p-values and traits
            assoc_url = f"{self.base_url}/singleNucleotidePolymorphisms/{query}/associations"
            assoc_data, _ = await self._cached_get(assoc_url)
            data["_associations"] = assoc_data.get("_embedded", {}).get("associations", []) if assoc_data else []
            
            # Fetch genomic contexts for mapped genes
            ctx_url = f"{self.base_url}/singleNucleotidePolymorphisms/{query}/genomicContexts"
            ctx_data, _ = await self._cached_get(ctx_url)
            data["_genomicContexts"] = ctx_data.get("_embedded", {}).get("genomicContexts", []) if ctx_data else []
            
            results.append(data)
        return results

    def normalize(self, raw_data: Dict[str, Any]) -> VariantEntity:
        rs_id = raw_data.get("rsId", "")
        
        # Parse mapped genes
        mapped_genes = []
        for ctx in raw_data.get("_genomicContexts", []):
            gene_dict = ctx.get("gene", {})
            if gene_dict.get("geneName"):
                mapped_genes.append({
                    "gene_name": gene_dict.get("geneName"),
                    "distance": ctx.get("distance"),
                    "is_mapped": ctx.get("isMappedGene", False),
                    "source": "GWAS Catalog"
                })
                
        # Parse associations (diseases/traits, p-values, study metadata)
        associations = raw_data.get("_associations", [])
        best_p_value = 1.0
        clinical_traits = []
        for assoc in associations:
            p_val = assoc.get("pvalue", 1.0)
            if p_val and p_val < best_p_value:
                best_p_value = p_val
            
            for trait in assoc.get("diseaseTraits", []):
                clinical_traits.append(trait.get("trait"))
                
        # Gene prioritization scoring (GWAS + OpenTargets concept)
        # We translate the GWAS p-value into a significance score between 0 and 1
        # where smaller p-value (e.g., 5e-8) -> higher score.
        gwas_score = 0.0
        if best_p_value < 5e-8:
            gwas_score = 1.0
        elif best_p_value < 1e-5:
            gwas_score = 0.8
        elif best_p_value < 0.05:
            gwas_score = 0.5
            
        clinical_sig = ", ".join(set(filter(None, clinical_traits)))

        variant = VariantEntity(
            rs_id=rs_id,
            canonical_name=rs_id,
            description=f"Variant associated with {clinical_sig}" if clinical_sig else "GWAS Variant",
            clinical_significance=clinical_sig,
            mapped_genes=mapped_genes,
            gwas_significance=gwas_score
        )
        variant.provenance.append(
            self._prov(url=f"{self.base_url}/singleNucleotidePolymorphisms/{rs_id}", confidence=0.9).model_dump()
        )
        return variant
