"""gnomAD connector — free, no API key.

Genome/exome variant frequencies from 76K+ individuals.
API Reference: https://gnomad.broadinstitute.org/api
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector


class GnomadConnector(BaseConnector):
    name = "gnomAD"
    BASE_URL = "https://gnomad.broadinstitute.org/api"
    cache_ttl = 86400

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        results = []

        # 1) Gene constraint data
        gql_gene = """
        query GeneSearch($gene: String!) {
            gene(gene_symbol: $gene, reference_genome: GRCh38) {
                gene_id
                symbol
                name
                chrom
                start
                stop
                gnomad_constraint {
                    pLI
                    oe_lof
                    oe_mis
                }
                clinvar_variants {
                    variant_id
                    clinical_significance
                    clinvar_variation_id
                    gold_stars
                    major_consequence
                    pos
                }
            }
        }
        """
        data, meta = await self._cached_post(
            self.BASE_URL,
            json_body={"query": gql_gene, "variables": {"gene": query}},
        )
        if not data or "data" not in data:
            return []
        gene = data["data"].get("gene")
        if not gene:
            return []

        constraint = gene.get("gnomad_constraint") or {}
        gene_id = gene.get("gene_id", "")
        symbol = gene.get("symbol", "")

        # Gene-level constraint record
        results.append({
            "id": gene_id,
            "entity_type": "gene",
            "data_type": "constraint",
            "canonical_name": symbol,
            "description": gene.get("name", ""),
            "chromosome": gene.get("chrom", ""),
            "pLI": constraint.get("pLI"),
            "oe_lof": constraint.get("oe_lof"),
            "oe_mis": constraint.get("oe_mis"),
            "provenance": [self._prov(
                url=f"https://gnomad.broadinstitute.org/gene/{gene_id}",
                ext_id=gene_id, confidence=1.0, reasoning="gnomAD constraint"
            ).to_dict()],
        })

        # 2) ClinVar variants — pathogenic/likely pathogenic only
        clinvar = gene.get("clinvar_variants") or []
        pathogenic = [v for v in clinvar
                      if v.get("clinical_significance") and
                      any(s in v["clinical_significance"].lower()
                          for s in ("pathogenic", "risk_factor"))]
        for v in pathogenic[:limit - 1]:
            vid = v.get("variant_id", "")
            results.append({
                "id": vid,
                "entity_type": "variant",
                "data_type": "clinvar",
                "canonical_name": vid,
                "gene": symbol,
                "clinical_significance": v.get("clinical_significance", ""),
                "consequence": v.get("major_consequence", ""),
                "position": v.get("pos"),
                "gold_stars": v.get("gold_stars"),
                "provenance": [self._prov(
                    url=f"https://gnomad.broadinstitute.org/variant/{vid}",
                    ext_id=str(v.get("clinvar_variation_id", "")),
                    confidence=0.95, reasoning="gnomAD ClinVar"
                ).to_dict()],
            })
            if len(results) >= limit:
                break

        return results
