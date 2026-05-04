# Clinical Workflow Guide

## Overview

The Clinical Workflow module processes clinical data through a comprehensive 10-stage pipeline, from EHR ingestion to therapy stratification. This guide provides detailed instructions for using the clinical workflow features.

**Task**: 17.2 Write user documentation  
**Priority**: P2  
**Requirements**: Documentation

## Table of Contents

1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [The 10-Stage Pipeline](#the-10-stage-pipeline)
4. [Step-by-Step Guide](#step-by-step-guide)
5. [PHI Protection](#phi-protection)
6. [Performance SLAs](#performance-slas)
7. [Troubleshooting](#troubleshooting)

## Introduction

The Clinical Workflow module is designed for translational researchers and clinicians who need to:

- Process electronic health records (EHR)
- Analyze patient phenotypes
- Evaluate tissue samples
- Quantify biomarkers
- Analyze genomic data
- Predict variant pathogenicity
- Model disease mechanisms
- Match patients to therapies

## Prerequisites

### Required Data

- **EHR Data**: HL7 v2/v3, FHIR R4, or CDA format
- **Tissue Images** (optional): WSI format (SVS, TIFF, NDPI)
- **Flow Cytometry Data** (optional): FCS format
- **Genomic Data** (optional): VCF 4.2+ format

### Permissions

- **Role**: Owner or Collaborator
- **HIPAA Training**: Required for handling PHI
- **Data Access**: Appropriate IRB approval

### System Requirements

- **Browser**: Chrome 90+, Firefox 88+, Safari 14+
- **Internet**: Stable connection (recommended: 10+ Mbps)
- **Storage**: Sufficient for data uploads (varies by dataset size)

## The 10-Stage Pipeline

### Stage 1: EHR Ingestion

**Purpose**: Import and structure electronic health records

**Input**: Raw EHR data (HL7, FHIR, CDA)  
**Output**: Structured clinical data with PHI redaction  
**SLA**: <5 seconds per record

**What it does**:
- Parses EHR formats
- Extracts structured fields (diagnoses, medications, procedures)
- Detects and redacts PHI
- Normalizes medical terminology

### Stage 2: Phenotype Clustering

**Purpose**: Group patients by similar phenotypes

**Input**: Structured clinical data from Stage 1  
**Output**: Phenotype clusters with rarity scores  
**SLA**: <30 seconds for 1000 patients

**What it does**:
- Embeds phenotype terms using sentence transformers
- Clusters using HDBSCAN algorithm
- Maps to HPO (Human Phenotype Ontology)
- Identifies rare symptom combinations

### Stage 3: Tissue Analysis

**Purpose**: Analyze histopathology images

**Input**: Whole slide images (WSI)  
**Output**: Detected anomalies with heatmaps  
**SLA**: <2 minutes per WSI

**What it does**:
- Processes high-resolution tissue images
- Detects anomalies (villous atrophy, infiltrates, dysplasia)
- Generates attention heatmaps (Grad-CAM)
- Provides confidence scores

### Stage 4: Biomarker Quantification

**Purpose**: Quantify flow cytometry data

**Input**: Flow cytometry files (FCS)  
**Output**: Cell population percentages  
**SLA**: <30 seconds per sample

**What it does**:
- Automated gating for 20+ cell populations
- Quantifies CD4+, CD8+, B cells, NK cells, etc.
- Flags abnormal populations
- Compares to reference ranges

### Stage 5: Genomic Sequencing

**Purpose**: Process genomic variant data

**Input**: VCF files (whole exome or genome)  
**Output**: Annotated variants  
**SLA**: <10 minutes for WES, <60 minutes for WGS

**What it does**:
- Parses VCF format
- Filters by quality scores
- Annotates with functional predictions
- Looks up population frequencies (gnomAD)

### Stage 6: Pathogenicity Prediction

**Purpose**: Predict variant pathogenicity

**Input**: Variants from Stage 5  
**Output**: Pathogenicity scores and classifications  
**SLA**: <1 minute for 1000 variants

**What it does**:
- Deep learning model inference
- Conformal prediction for confidence intervals
- ACMG/AMP guideline classification
- SHAP explainability

### Stage 7: Knowledge Graph Cross-Reference

**Purpose**: Link variants to biomedical knowledge

**Input**: Variants and genes from previous stages  
**Output**: Gene-disease-pathway associations  
**SLA**: <500ms per query

**What it does**:
- Queries Neo4j knowledge graph
- Cross-references with DisGeNET, OpenTargets, OMIM
- Builds association maps
- Detects contradictions

### Stage 8: Disruption Modeling

**Purpose**: Simulate mutation effects

**Input**: Pathogenic variants from Stage 6  
**Output**: Pathway disruption models  
**SLA**: <30 seconds per mutation

**What it does**:
- Simulates cellular pathway effects
- Models transcriptional regulation
- Predicts immune dysregulation
- Quantifies disruption scores

### Stage 9: Drug Matching

**Purpose**: Match pathways to treatments

**Input**: Disrupted pathways from Stage 8  
**Output**: Ranked drug candidates  
**SLA**: <30 seconds

**What it does**:
- AI recommender system
- Integrates DrugBank, ChEMBL, PubChem
- Aligns mechanisms of action
- Provides safety profiles

### Stage 10: Therapy Stratification

**Purpose**: Calculate therapy compatibility

**Input**: Patient profile and genetic data  
**Output**: Therapy compatibility scores  
**SLA**: <10 seconds

**What it does**:
- Scores stem cell transplant compatibility
- Evaluates bone marrow transplant eligibility
- Performs HLA matching
- Conducts risk-benefit analysis

## Step-by-Step Guide

### Starting a Clinical Workflow

1. **Navigate to Clinical Workflow**
   - Click "Clinical Workflow" in the navigation menu

2. **Create New Workflow**
   - Click "Start New Workflow"
   - Enter workflow name (e.g., "Patient 001 Analysis")
   - Select project

3. **Upload EHR Data**
   - Click "Upload EHR Data"
   - Select file (HL7, FHIR, or CDA)
   - Verify patient ID is anonymized
   - Click "Upload"

4. **Configure Workflow**
   - Select which stages to run (all 10 by default)
   - Configure stage-specific settings
   - Review PHI protection settings

5. **Start Workflow**
   - Review configuration
   - Click "Start Workflow"
   - Workflow begins processing

### Monitoring Progress

The workflow provides real-time updates:

- **Progress Bar**: Overall completion (0-100%)
- **Current Stage**: Which stage is running
- **Stage Status**: Pending, Running, Completed, Failed
- **Estimated Time**: Time remaining
- **WebSocket Updates**: Real-time progress messages

### Reviewing Results

After completion:

1. **Navigate to Results**
   - Click on completed workflow
   - View results for each stage

2. **Stage 1 Results: EHR Ingestion**
   - Structured phenotypes
   - Extracted medications
   - Identified diagnoses
   - PHI redaction report

3. **Stage 2 Results: Phenotype Clustering**
   - Cluster assignments
   - Rarity scores
   - Representative terms
   - Visualization (t-SNE plot)

4. **Stage 3 Results: Tissue Analysis**
   - Detected anomalies
   - Confidence scores
   - Attention heatmaps
   - Annotated images

5. **Stage 4 Results: Biomarker Quantification**
   - Cell population percentages
   - Abnormal flags
   - Reference comparisons
   - Gating strategy

6. **Stage 5 Results: Genomic Sequencing**
   - Variant list
   - Quality scores
   - Population frequencies
   - Functional annotations

7. **Stage 6 Results: Pathogenicity Prediction**
   - Pathogenicity scores
   - ACMG/AMP classifications
   - Confidence intervals
   - Feature importance

8. **Stage 7 Results: Knowledge Graph**
   - Gene-disease associations
   - Pathway memberships
   - Literature evidence
   - Contradictions

9. **Stage 8 Results: Disruption Modeling**
   - Affected pathways
   - Transcriptional impacts
   - Immune dysregulation
   - Disruption scores

10. **Stage 9 Results: Drug Matching**
    - Ranked drug candidates
    - Mechanisms of action
    - Safety profiles
    - Evidence summaries

11. **Stage 10 Results: Therapy Stratification**
    - Compatibility scores
    - Eligibility assessments
    - Risk-benefit analysis
    - Treatment timelines

### Exporting Results

1. **Select Export Format**
   - PDF: Comprehensive report
   - DOCX: Editable document
   - JSON: Machine-readable
   - CSV: Tabular data

2. **Configure Export**
   - Select stages to include
   - Include/exclude PHI (if authorized)
   - Add custom notes

3. **Download**
   - Click "Export"
   - Wait for generation
   - Download file

## PHI Protection

### Automatic PHI Detection

The system automatically detects and redacts:

- **Names**: Patient names, provider names
- **Dates**: Birth dates, admission dates, discharge dates
- **Locations**: Addresses, cities, ZIP codes
- **IDs**: SSN, medical record numbers, insurance IDs
- **Contact**: Phone numbers, email addresses

### PHI Redaction

Detected PHI is replaced with:

- `[NAME]` for names
- `[DATE]` for dates
- `[LOCATION]` for addresses
- `[ID]` for identifiers
- `[PHONE]` for phone numbers
- `[EMAIL]` for email addresses

### Verification

After Stage 1 (EHR Ingestion):

1. Review PHI redaction report
2. Verify all PHI is redacted
3. Report any missed PHI immediately

### Audit Trail

All PHI access is logged:

- User ID
- Timestamp
- Action (view, export, etc.)
- IP address (hashed)
- Data accessed

## Performance SLAs

### Stage Performance Targets

| Stage | SLA Target | Typical Time |
|-------|------------|--------------|
| 1. EHR Ingestion | <5s per record | 2-3s |
| 2. Phenotype Clustering | <30s for 1000 patients | 15-20s |
| 3. Tissue Analysis | <2min per WSI | 60-90s |
| 4. Biomarker Quantification | <30s per sample | 15-20s |
| 5. Genomic Sequencing | <10min for WES | 5-8min |
| 6. Pathogenicity Prediction | <1min for 1000 variants | 30-45s |
| 7. Knowledge Graph | <500ms per query | 200-300ms |
| 8. Disruption Modeling | <30s per mutation | 15-20s |
| 9. Drug Matching | <30s | 15-20s |
| 10. Therapy Stratification | <10s | 5-7s |

### Full Pipeline

- **Target**: <30 minutes for complete 10-stage pipeline
- **Typical**: 20-25 minutes

### Monitoring Performance

View performance metrics:

1. Navigate to **Runtime** → **Diagnostics**
2. View stage-specific latencies
3. Check SLA compliance
4. Review performance trends

## Troubleshooting

### Common Issues

#### Stage 1: "EHR format not recognized"

**Solution**: Verify file is in HL7, FHIR, or CDA format

#### Stage 2: "Insufficient data for clustering"

**Solution**: Provide at least 10 patient records

#### Stage 3: "Image format not supported"

**Solution**: Convert to SVS, TIFF, or NDPI format

#### Stage 4: "FCS file corrupted"

**Solution**: Re-export from flow cytometer

#### Stage 5: "VCF validation failed"

**Solution**: Ensure VCF 4.2+ format with proper headers

#### Stage 6: "Model inference timeout"

**Solution**: Reduce batch size or try again

#### Stage 7: "Knowledge graph unavailable"

**Solution**: Wait for automatic recovery (5 minutes)

#### Stage 8: "Pathway simulation failed"

**Solution**: Check variant annotations are complete

#### Stage 9: "No drug matches found"

**Solution**: Verify disrupted pathways are identified

#### Stage 10: "HLA data missing"

**Solution**: Provide HLA typing data

### Getting Help

- **Documentation**: This guide
- **Support**: support@drugdesigner.com
- **Emergency**: For PHI issues, contact immediately

---

**Last Updated**: Task 17.2 Implementation  
**Version**: 1.0  
**Status**: Complete
