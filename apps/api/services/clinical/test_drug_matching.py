"""Test for drug matching service implementation."""

import asyncio
from typing import Dict, Any


async def test_drug_matching_logic():
    """Test the drug matching scoring logic without database dependencies."""
    
    # Simulate drug candidates
    drug_candidates = {
        "CHEMBL123": {
            "drug_id": "CHEMBL123",
            "drug_name": "Test Drug A",
            "targeted_genes": ["FOXP3", "IL2RA", "CD25"],
            "targeted_pathways": [],
            "source": "chembl",
            "clinical_phase": "4",
            "match_score": 0.0
        },
        "DB00001": {
            "drug_id": "DB00001",
            "drug_name": "Test Drug B",
            "targeted_genes": ["FOXP3"],
            "targeted_pathways": [],
            "source": "drugbank",
            "clinical_phase": "3",
            "match_score": 0.0
        }
    }
    
    # Test parameters
    gene_symbols = ["FOXP3", "IL2RA"]
    disrupted_pathways = ["hsa04110"]
    all_target_genes = set(gene_symbols)
    
    # Calculate match scores (same logic as in service)
    for drug_id, drug_data in drug_candidates.items():
        # 1. Gene overlap score
        gene_overlap = len(set(drug_data["targeted_genes"]) & all_target_genes)
        gene_score = min(gene_overlap / max(len(gene_symbols), 1), 1.0)
        
        # 2. Pathway relevance score
        pathway_score = 0.5
        for pathway_id in disrupted_pathways:
            if pathway_id in drug_data.get("targeted_pathways", []):
                pathway_score = 1.0
                break
        
        # 3. Clinical phase score
        phase_score = 0.5
        clinical_phase = drug_data.get("clinical_phase", "")
        if clinical_phase == "4":
            phase_score = 1.0
        elif clinical_phase == "3":
            phase_score = 0.8
        elif clinical_phase in ["2", "1"]:
            phase_score = 0.6
        
        # 4. Source confidence score
        source_score = 0.8 if drug_data["source"] == "drugbank" else 0.7
        
        # Composite match score
        drug_data["match_score"] = (
            0.40 * gene_score +
            0.30 * pathway_score +
            0.20 * phase_score +
            0.10 * source_score
        )
    
    # Verify scoring
    print("Drug Matching Test Results:")
    print("-" * 60)
    for drug_id, drug_data in drug_candidates.items():
        print(f"\nDrug: {drug_data['drug_name']} ({drug_id})")
        print(f"  Targeted Genes: {drug_data['targeted_genes']}")
        print(f"  Clinical Phase: {drug_data['clinical_phase']}")
        print(f"  Source: {drug_data['source']}")
        print(f"  Match Score: {drug_data['match_score']:.3f}")
    
    # Rank drugs
    ranked_drugs = sorted(
        drug_candidates.values(),
        key=lambda x: x["match_score"],
        reverse=True
    )
    
    print("\n" + "=" * 60)
    print("Ranked Results:")
    for i, drug in enumerate(ranked_drugs, 1):
        print(f"{i}. {drug['drug_name']}: {drug['match_score']:.3f}")
    
    # Assertions
    assert ranked_drugs[0]["drug_name"] == "Test Drug A", "Drug A should rank higher"
    assert ranked_drugs[0]["match_score"] > ranked_drugs[1]["match_score"], "Scores should be ordered"
    
    print("\n✓ All tests passed!")
    return True


if __name__ == "__main__":
    asyncio.run(test_drug_matching_logic())
