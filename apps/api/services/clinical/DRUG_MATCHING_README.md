# Drug Matching Service Implementation

## Overview

The drug matching service implements an AI-based recommender system for identifying targeted therapies based on disrupted pathways and genetic variants. This is **Stage 9** of the 10-stage clinical workflow pipeline.

## Requirements

- **FR-API-001**: Clinical Workflow Endpoints
- **FR-CLIN-009**: Stage 9 - AI Targeted Drug Matching
- **Performance Target**: p95 <30s for drug matching

## Architecture

### Data Sources

The service integrates with multiple external databases:

1. **DrugBank** - FDA-approved drugs and drug-target relationships
2. **ChEMBL** - Bioactivity data and clinical phase information
3. **PubChem** - Chemical structures and properties
4. **KEGG** - Pathway-gene relationships
5. **Reactome** - Pathway-gene relationships

### Algorithm

The drug matching algorithm uses a **collaborative filtering** approach with the following steps:

#### Step 1: Pathway Expansion
- Expands disrupted pathways to identify all genes involved
- Queries KEGG for pathways starting with "hsa" or "path:"
- Queries Reactome for pathways starting with "R-HSA"
- Combines pathway genes with input gene symbols

#### Step 2: Drug Candidate Discovery
- Queries DrugBank for drugs targeting each gene (limit: 50 genes)
- Queries ChEMBL for bioactivity data (limit: 30 genes)
- Aggregates drug candidates with their targeted genes

#### Step 3: Match Score Calculation

The match score is a weighted composite of 4 components:

```
Match Score = 0.40 × Gene Overlap Score
            + 0.30 × Pathway Relevance Score
            + 0.20 × Clinical Phase Score
            + 0.10 × Source Confidence Score
```

**Component Details:**

1. **Gene Overlap Score** (40% weight)
   - Measures how many target genes match the input genes
   - Formula: `min(gene_overlap / input_genes, 1.0)`
   - Range: 0.0 - 1.0

2. **Pathway Relevance Score** (30% weight)
   - Checks if drug targets disrupted pathways
   - 1.0 if pathway match found, 0.5 otherwise
   - Range: 0.5 - 1.0

3. **Clinical Phase Score** (20% weight)
   - Prefers FDA-approved drugs over experimental ones
   - Phase 4 / FDA approved: 1.0
   - Phase 3: 0.8
   - Phase 2/1: 0.6
   - Unknown: 0.5

4. **Source Confidence Score** (10% weight)
   - DrugBank: 0.8 (curated, FDA-focused)
   - ChEMBL: 0.7 (broader, includes experimental)

#### Step 4: Ranking and Filtering
- Ranks all candidates by match score (descending)
- Selects top 20 candidates
- Enriches top 10 with detailed information

#### Step 5: Patient Context Adjustment
- Applies patient-specific filters if context provided
- Age < 18: Reduces score by 20% (limited pediatric data)
- Hepatic impairment: Reduces score by 10%
- Renal impairment: Reduces score by 10%

## API Endpoint

### POST /api/v1/clinical/drug-match

**Request:**
```json
{
  "disrupted_pathways": ["hsa04110", "R-HSA-1640170"],
  "gene_symbols": ["FOXP3", "IL2RA", "CD25"],
  "patient_context": {
    "age": 45,
    "comorbidities": ["hepatic_impairment"],
    "current_medications": []
  },
  "project_id": "uuid"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "run_id": "uuid",
    "drug_matches": [
      {
        "drug_id": "CHEMBL123",
        "drug_name": "Example Drug",
        "drugbank_id": "DB00001",
        "chembl_id": "CHEMBL123",
        "match_score": 0.820,
        "targeted_pathways": ["hsa04110"],
        "targeted_genes": ["FOXP3", "IL2RA"],
        "mechanism_of_action": "Targets FOXP3, IL2RA",
        "drug_class": "Small molecule",
        "approval_status": "FDA approved",
        "url": "https://www.ebi.ac.uk/chembl/...",
        "safety_profile": {
          "common_adverse_events": ["Fatigue", "Nausea"],
          "serious_adverse_events": [],
          "contraindications": [],
          "drug_interactions": [],
          "black_box_warnings": []
        },
        "clinical_evidence": {
          "phase_3_trials": 0,
          "phase_2_trials": 0,
          "efficacy_rate": "Unknown",
          "references": []
        }
      }
    ],
    "summary": {
      "total_matches": 10,
      "fda_approved": 5,
      "clinical_trial": 5,
      "high_confidence": 3,
      "pathways_targeted": 2,
      "genes_targeted": 15,
      "pathway_genes_expanded": 12
    },
    "model_info": {
      "model_version": "drug_matching_recommender_v1.0",
      "recommendation_method": "Collaborative filtering + knowledge graph",
      "data_sources": ["DrugBank", "ChEMBL", "PubChem", "KEGG", "Reactome"],
      "scoring_components": {
        "gene_overlap": 0.40,
        "pathway_relevance": 0.30,
        "clinical_phase": 0.20,
        "source_confidence": 0.10
      }
    }
  },
  "provenance": {
    "sources_queried": ["drugbank", "chembl", "kegg", "reactome"],
    "sources_succeeded": ["drugbank", "chembl", "kegg", "reactome"],
    "model_version": "drug_matching_recommender_v1.0",
    "generated_at": "2024-01-15T10:30:00Z"
  }
}
```

## Performance Characteristics

- **Target Performance**: p95 <30s
- **Pathway Expansion**: ~1-2s per pathway
- **Drug Discovery**: ~0.5s per gene (parallelizable)
- **Scoring**: <1s for all candidates
- **Total Expected**: 10-25s for typical queries

### Performance Optimizations

1. **Connector Caching**: All connector queries use 2-tier cache (Redis + in-memory)
2. **Rate Limiting**: Per-connector rate limits prevent API throttling
3. **Gene Limits**: Limits to 50 genes for DrugBank, 30 for ChEMBL
4. **Candidate Limits**: Top 20 candidates ranked, top 10 enriched

## Error Handling

- **Pathway Expansion Failures**: Logged as warnings, continue with available data
- **Connector Failures**: Logged as warnings, continue with other sources
- **Complete Failure**: Run marked as FAILED, error details stored in run.errors

## Testing

Run the test suite:
```bash
python apps/api/services/clinical/test_drug_matching.py
```

Expected output:
```
Drug Matching Test Results:
------------------------------------------------------------
Drug: Test Drug A (CHEMBL123)
  Targeted Genes: ['FOXP3', 'IL2RA', 'CD25']
  Clinical Phase: 4
  Source: chembl
  Match Score: 0.820

Drug: Test Drug B (DB00001)
  Targeted Genes: ['FOXP3']
  Clinical Phase: 3
  Source: drugbank
  Match Score: 0.590

============================================================
Ranked Results:
1. Test Drug A: 0.820
2. Test Drug B: 0.590

✓ All tests passed!
```

## Future Enhancements

1. **Clinical Trial Integration**: Query ClinicalTrials.gov for efficacy data
2. **Safety Profile Enrichment**: Query SIDER database for adverse events
3. **Drug-Drug Interaction Checking**: Integrate with DrugBank DDI data
4. **Mechanism of Action Alignment**: Use pathway overlap scoring
5. **Literature Evidence**: Query PubMed for drug-disease associations
6. **Machine Learning Model**: Train a neural network on historical drug-disease outcomes

## Dependencies

- `connectors.drugbank.DrugBankConnector`
- `connectors.chembl.ChEMBLConnector`
- `connectors.pubchem.PubChemConnector`
- `connectors.kegg.KEGGConnector`
- `connectors.reactome.ReactomeConnector`
- `core.audit.log_audit_event`
- `core.provenance.create_provenance_record`
- `models.db_tables.Run`

## Audit Logging

All drug matching operations are logged with:
- User ID
- Project ID
- Run ID
- Pathway count
- Gene count
- Match count
- Elapsed time (ms)

## Provenance Tracking

Complete provenance includes:
- Sources queried
- Sources succeeded
- Model version
- Generation timestamp
- Input snapshot (pathways, genes, patient context)
