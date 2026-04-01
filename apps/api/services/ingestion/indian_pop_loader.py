"""Indian demographic dataset loader for IndiGen, IGVDB, and GenomeAsia variant data.

This loader reads variant frequency data from local TSV/VCF files you download from:
- IndiGen:    https://clingen.igib.res.in/indigen/
- IGVDB:      https://www.igvdb.res.in/
- GenomeAsia: https://genomeasia100k.org/

Place downloaded files as TSV under:
  {data_dir}/<source_name>/variants.tsv
Expected TSV columns: rsid, allele_frequency, gene, consequence (at minimum)

If the data files are absent, search() raises DataFilesNotFound with actionable guidance
rather than silently returning an empty list.
"""

import csv
from pathlib import Path
from typing import Any, Dict, List
import structlog

from connectors.base import BaseConnector
from models.entities import VariantEntity

log = structlog.get_logger()


class DataFilesNotFound(RuntimeError):
    """Raised when Indian population data files are not present in data_dir."""
    pass


class IndianPopLoader(BaseConnector):
    """File-based loader for IndiGen, IGVDB, and GenomeAsia variant datasets.

    Searches local TSV files for variants matching the query (gene name or rsID).
    Call search() with a gene symbol (e.g. "BRCA1") or rsID (e.g. "rs28897696").
    """

    name = "IndianDemographics"
    SUPPORTED_SOURCES = ("indigen", "igvdb", "genomeasia")

    def __init__(self, data_dir: str = "./data/raw/indian_pop"):
        super().__init__()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_available_files(self) -> Dict[str, Path]:
        """Return {source_name: tsv_path} for all variant TSV files that actually exist."""
        found: Dict[str, Path] = {}
        for source in self.SUPPORTED_SOURCES:
            candidates = [
                self.data_dir / source / "variants.tsv",
                self.data_dir / f"{source}_variants.tsv",
                self.data_dir / f"{source}.tsv",
            ]
            for path in candidates:
                if path.exists() and path.stat().st_size > 0:
                    found[source] = path
                    break
        return found

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search local TSV variant files for the given gene name or rsID.

        Raises DataFilesNotFound if no data files are present in data_dir.
        Returns matching variant records derived from real file content.
        """
        available = self._get_available_files()

        if not available:
            raise DataFilesNotFound(
                f"No Indian population variant data files found under '{self.data_dir}'. "
                f"Expected TSV files for sources: {', '.join(self.SUPPORTED_SOURCES)}. "
                "Download datasets and place them under "
                f"'{self.data_dir}/<source_name>/variants.tsv'. "
                "Sources: IndiGen (https://clingen.igib.res.in/indigen/), "
                "IGVDB (https://www.igvdb.res.in/), "
                "GenomeAsia (https://genomeasia100k.org/)."
            )

        query_lower = query.lower().strip()
        results: List[Dict[str, Any]] = []

        for source, tsv_path in available.items():
            try:
                with open(tsv_path, encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f, delimiter="\t")
                    for row in reader:
                        if len(results) >= limit:
                            break
                        rsid = row.get("rsid", row.get("rs_id", "")).lower()
                        gene = row.get("gene", row.get("gene_name", "")).lower()
                        if query_lower not in rsid and query_lower not in gene:
                            continue

                        freq_raw = row.get("allele_frequency", row.get("af", "0"))
                        try:
                            freq = float(freq_raw)
                        except (ValueError, TypeError):
                            freq = 0.0

                        ent = self.normalize({
                            "rsid": row.get("rsid", row.get("rs_id", f"rs_unknown_{source}")),
                            "allele_frequency": freq,
                            "source": source.upper(),
                            "gene": row.get("gene", row.get("gene_name", "")),
                            "consequence": row.get("consequence", row.get("variant_type", "")),
                        })
                        results.append(ent.model_dump() if hasattr(ent, "model_dump") else ent.__dict__)

            except (OSError, csv.Error) as exc:
                log.warning("indian_pop_loader.read_error",
                            source=source, path=str(tsv_path), error=str(exc))
                continue

        log.info(
            "indian_pop_loader.search",
            query=query,
            sources_searched=list(available.keys()),
            results=len(results),
        )
        return results

    def normalize(self, raw_data: Dict[str, Any]) -> VariantEntity:
        rsid = raw_data.get("rsid", "unknown")
        freq = raw_data.get("allele_frequency", 0.0)
        source = raw_data.get("source", "IndiGen")
        gene = raw_data.get("gene", "")
        consequence = raw_data.get("consequence", "")

        return VariantEntity(
            canonical_name=rsid,
            rs_id=rsid,
            gene=gene,
            consequence=consequence,
            population_frequencies={"SAS": freq},
            indian_demographic_context=(
                f"Recorded in {source} with allele frequency {freq:.4f} in South Asian cohort"
            ),
            description=(
                f"Variant {rsid} in gene {gene} from {source} "
                f"(consequence: {consequence or 'unknown'})"
            ),
            provenance=[self._prov(
                url=f"local://indian_pop/{source.lower()}",
                ext_id=rsid,
                confidence=0.98,
                reasoning=f"Local demographic dataset {source} — parsed from TSV",
            ).model_dump()]
        )
