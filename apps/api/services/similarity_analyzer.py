"""Biomedical evidence similarity detection and clustering.

Uses the NLP Contradiction Engine for cosine similarity when available,
falling back to Jaccard keyword overlap. Provides agglomerative clustering,
entity extraction, relationship classification, and filtering.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


# ── Data Models ─────────────────────────────────────────────


class ClaimItem(BaseModel):
    """A single evidence claim with metadata."""

    text: str
    source_db: str = "unknown"
    entity_type: str = "unknown"
    entity_id: str = ""
    entity_name: str = ""
    year: Optional[int] = None
    url: str = ""


class EntityMention(BaseModel):
    """A recognized biomedical entity mention."""

    name: str
    entity_type: Literal["gene", "protein", "drug", "disease", "pathway"]


class SimilarityPair(BaseModel):
    """A pair of similar claims with their relationship."""

    claim_a: ClaimItem
    claim_b: ClaimItem
    similarity_score: float = Field(ge=-1.0, le=1.0)
    relationship_type: Literal["shared_finding", "complementary_evidence"]
    shared_entities: List[str] = Field(default_factory=list)


class SimilarityCluster(BaseModel):
    """A cluster of similar evidence items."""

    cluster_id: str
    members: List[Dict[str, Any]]
    member_count: int
    similarity_score: float = Field(ge=0.0, le=1.0)
    relationship_type: Literal["shared_finding", "complementary_evidence"] = "shared_finding"
    shared_entities: List[str] = Field(default_factory=list)
    representative_summary: str = ""
    consensus_strength: Literal["strong", "moderate", "weak"] = "moderate"


class SimilarityResult(BaseModel):
    """Complete similarity analysis result."""

    pairs: List[SimilarityPair] = Field(default_factory=list)
    clusters: List[SimilarityCluster] = Field(default_factory=list)
    total_claims: int = 0
    method_used: Literal["nlp", "keyword_fallback"] = "keyword_fallback"


# ── Entity extraction patterns ──────────────────────────────

_GENE_PAT = re.compile(
    r"\b([A-Z][A-Z0-9]{1,6}(?:-[A-Z0-9]+)?)\b"
)  # e.g., BRCA1, TP53, PIK3CA

_DRUG_PAT = re.compile(
    r"\b(aspirin|ibuprofen|metformin|tamoxifen|cisplatin|doxorubicin|"
    r"paclitaxel|erlotinib|gefitinib|sorafenib|bevacizumab|trastuzumab|"
    r"nivolumab|pembrolizumab|rituximab|imatinib|sunitinib|lapatinib|"
    r"vemurafenib|olaparib|palbociclib|osimertinib|atezolizumab)\b",
    re.I,
)

_DISEASE_PAT = re.compile(
    r"\b(cancer|carcinoma|melanoma|leukemia|lymphoma|diabetes|alzheimer|"
    r"parkinson|asthma|arthritis|hypertension|obesity|fibrosis|"
    r"hepatitis|tuberculosis|malaria|HIV|COVID|SARS|influenza|"
    r"glioblastoma|neuroblastoma|sarcoma|myeloma)\b",
    re.I,
)

_PATHWAY_PAT = re.compile(
    r"\b(MAPK|PI3K|Wnt|Notch|Hedgehog|NF-kB|JAK-STAT|TGF-beta|"
    r"mTOR|AMPK|apoptosis|autophagy|glycolysis|oxidative phosphorylation|"
    r"cell cycle|DNA repair|p53 pathway|RAS signaling)\b",
    re.I,
)

_PROTEIN_PAT = re.compile(
    r"\b(kinase|receptor|ligand|enzyme|antibody|cytokine|chemokine|"
    r"integrin|collagen|actin|tubulin|histone|ubiquitin|caspase|"
    r"protease|phosphatase|transferase)\b",
    re.I,
)


def extract_entities(text: str) -> List[EntityMention]:
    """Extract biomedical entities from text.

    Returns a list of EntityMention with type and name.
    """
    entities: List[EntityMention] = []
    seen: Set[str] = set()

    for match in _GENE_PAT.finditer(text):
        name = match.group(1)
        # Filter out common English words that match the gene pattern
        if name.lower() in {"the", "and", "for", "not", "are", "was", "has", "had",
                            "but", "all", "can", "her", "his", "its", "may", "new",
                            "now", "old", "see", "way", "who", "did", "get", "let",
                            "say", "she", "too", "use", "via", "one", "two"}:
            continue
        key = f"gene:{name}"
        if key not in seen and len(name) >= 2:
            seen.add(key)
            entities.append(EntityMention(name=name, entity_type="gene"))

    for pat, etype in [
        (_DRUG_PAT, "drug"),
        (_DISEASE_PAT, "disease"),
        (_PATHWAY_PAT, "pathway"),
        (_PROTEIN_PAT, "protein"),
    ]:
        for match in pat.finditer(text):
            name = match.group(0)
            key = f"{etype}:{name.lower()}"
            if key not in seen:
                seen.add(key)
                entities.append(EntityMention(name=name, entity_type=etype))  # type: ignore[arg-type]

    return entities


class SimilarityAnalyzer:
    """Biomedical evidence similarity detection and clustering."""

    def __init__(self, threshold: float = 0.7) -> None:
        self._threshold = threshold

    async def find_similarities(
        self, claims: List[ClaimItem]
    ) -> SimilarityResult:
        """Compute pairwise similarities and cluster related claims.

        1. Encode all claims
        2. Compute pairwise cosine similarity matrix
        3. Filter pairs above threshold
        4. Classify: shared_finding vs complementary_evidence
        5. Cluster using agglomerative clustering
        6. Generate representative summary per cluster
        7. Extract shared entities per cluster
        """
        from services.nlp_contradiction_engine import get_nlp_engine

        engine = get_nlp_engine()
        await engine.initialize()

        if len(claims) < 2:
            return SimilarityResult(
                total_claims=len(claims),
                method_used=engine.get_method_used(),
            )

        # Compute pairwise similarities
        pairs: List[SimilarityPair] = []
        sim_matrix: Dict[Tuple[int, int], float] = {}

        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                sim = engine.compute_similarity(claims[i].text, claims[j].text)
                sim_matrix[(i, j)] = sim

                if sim >= self._threshold:
                    entities_a = set(e.name for e in extract_entities(claims[i].text))
                    entities_b = set(e.name for e in extract_entities(claims[j].text))
                    rel_type = self.classify_relationship(sim, entities_a, entities_b)
                    shared = list(entities_a & entities_b)

                    pairs.append(SimilarityPair(
                        claim_a=claims[i],
                        claim_b=claims[j],
                        similarity_score=round(sim, 4),
                        relationship_type=rel_type,
                        shared_entities=shared,
                    ))

        # Agglomerative clustering
        clusters = self._agglomerative_cluster(claims, sim_matrix)

        return SimilarityResult(
            pairs=pairs,
            clusters=clusters,
            total_claims=len(claims),
            method_used=engine.get_method_used(),
        )

    def classify_relationship(
        self,
        sim_score: float,
        entities_a: Set[str],
        entities_b: Set[str],
    ) -> Literal["shared_finding", "complementary_evidence"]:
        """Classify as shared_finding or complementary_evidence."""
        union = entities_a | entities_b
        entity_overlap = len(entities_a & entities_b) / max(len(union), 1)
        if entity_overlap > 0.6 and sim_score > 0.8:
            return "shared_finding"
        return "complementary_evidence"

    def filter_results(
        self,
        results: List[SimilarityCluster],
        entity_type: Optional[str] = None,
        source_db: Optional[str] = None,
    ) -> List[SimilarityCluster]:
        """Filter clusters by entity type or source database."""
        filtered: List[SimilarityCluster] = []
        for cluster in results:
            keep = True

            if source_db:
                has_source = any(
                    m.get("source_db", m.get("source", "")).lower() == source_db.lower()
                    for m in cluster.members
                )
                if not has_source:
                    keep = False

            if entity_type:
                # Check if any shared entity matches the type
                has_entity_type = False
                for member in cluster.members:
                    text = member.get("text", "")
                    entities = extract_entities(text)
                    if any(e.entity_type == entity_type for e in entities):
                        has_entity_type = True
                        break
                if not has_entity_type:
                    keep = False

            if keep:
                filtered.append(cluster)

        return filtered

    def _agglomerative_cluster(
        self,
        claims: List[ClaimItem],
        sim_matrix: Dict[Tuple[int, int], float],
    ) -> List[SimilarityCluster]:
        """Simple agglomerative clustering based on similarity threshold."""
        n = len(claims)
        # Each claim starts in its own cluster
        cluster_map: Dict[int, int] = {i: i for i in range(n)}

        # Merge clusters where similarity exceeds threshold
        for (i, j), sim in sorted(sim_matrix.items(), key=lambda x: -x[1]):
            if sim < self._threshold:
                break
            # Find root clusters
            root_i = self._find_root(cluster_map, i)
            root_j = self._find_root(cluster_map, j)
            if root_i != root_j:
                cluster_map[root_j] = root_i

        # Build cluster groups
        groups: Dict[int, List[int]] = {}
        for idx in range(n):
            root = self._find_root(cluster_map, idx)
            groups.setdefault(root, []).append(idx)

        # Convert to SimilarityCluster objects
        clusters: List[SimilarityCluster] = []
        for root, member_indices in groups.items():
            if len(member_indices) < 2:
                continue

            members = []
            all_entities: Set[str] = set()
            all_entity_names: List[str] = []

            for idx in member_indices:
                claim = claims[idx]
                members.append({
                    "text": claim.text[:200],
                    "source_db": claim.source_db,
                    "entity_type": claim.entity_type,
                    "entity_id": claim.entity_id,
                    "entity_name": claim.entity_name,
                })
                entities = extract_entities(claim.text)
                for e in entities:
                    all_entities.add(e.name)
                if claim.entity_name:
                    all_entity_names.append(claim.entity_name)

            # Compute average similarity within cluster
            sims = []
            for i_idx in range(len(member_indices)):
                for j_idx in range(i_idx + 1, len(member_indices)):
                    key = (min(member_indices[i_idx], member_indices[j_idx]),
                           max(member_indices[i_idx], member_indices[j_idx]))
                    if key in sim_matrix:
                        sims.append(sim_matrix[key])
            avg_sim = sum(sims) / len(sims) if sims else 0.5

            # Determine relationship type
            shared_entity_set: Set[str] = set()
            for i_idx in range(len(member_indices)):
                ents_i = set(e.name for e in extract_entities(claims[member_indices[i_idx]].text))
                for j_idx in range(i_idx + 1, len(member_indices)):
                    ents_j = set(e.name for e in extract_entities(claims[member_indices[j_idx]].text))
                    shared_entity_set |= (ents_i & ents_j)

            rel_type: Literal["shared_finding", "complementary_evidence"] = (
                "shared_finding" if avg_sim > 0.8 and len(shared_entity_set) > 0
                else "complementary_evidence"
            )

            # Generate representative summary
            summary = self._generate_summary(claims, member_indices)

            consensus: Literal["strong", "moderate", "weak"] = (
                "strong" if len(member_indices) >= 4
                else "moderate" if len(member_indices) >= 2
                else "weak"
            )

            clusters.append(SimilarityCluster(
                cluster_id=f"cluster_{uuid.uuid4().hex[:8]}",
                members=members,
                member_count=len(members),
                similarity_score=round(avg_sim, 3),
                relationship_type=rel_type,
                shared_entities=sorted(shared_entity_set)[:10],
                representative_summary=summary,
                consensus_strength=consensus,
            ))

        return clusters

    @staticmethod
    def _find_root(cluster_map: Dict[int, int], idx: int) -> int:
        """Find root of a cluster with path compression."""
        while cluster_map[idx] != idx:
            cluster_map[idx] = cluster_map[cluster_map[idx]]
            idx = cluster_map[idx]
        return idx

    @staticmethod
    def _generate_summary(claims: List[ClaimItem], indices: List[int]) -> str:
        """Generate a representative summary for a cluster."""
        if not indices:
            return ""
        # Use the shortest claim as representative (often most concise)
        texts = [claims[i].text for i in indices]
        shortest = min(texts, key=len)
        if len(shortest) > 150:
            shortest = shortest[:147] + "..."
        source_count = len(set(claims[i].source_db for i in indices))
        return f"{shortest} (supported by {len(indices)} sources from {source_count} database{'s' if source_count > 1 else ''})"
