# Drug Designer User Guide

## Welcome to Drug Designer

Drug Designer is a browser-native, evidence-first, provenance-first scientific research platform for drug discovery and translational research. This guide will help you get started and make the most of the platform's features.

**Task**: 17.2 Write user documentation  
**Priority**: P2  
**Requirements**: Documentation

## Table of Contents

1. [Getting Started](#getting-started)
2. [Core Concepts](#core-concepts)
3. [Module Guides](#module-guides)
   - [Disease Intelligence](#disease-intelligence)
   - [Target Discovery](#target-discovery)
   - [Clinical Workflow](#clinical-workflow)
   - [Evidence Management](#evidence-management)
   - [Dossier Generation](#dossier-generation)
4. [Advanced Features](#advanced-features)
5. [Troubleshooting](#troubleshooting)
6. [FAQ](#faq)

## Getting Started

### Creating an Account

1. Navigate to the Drug Designer platform
2. Click "Sign Up" in the top right corner
3. Enter your email, password, and display name
4. Click "Create Account"
5. Verify your email address (check your inbox)

### Creating Your First Project

1. Click "Projects" in the navigation menu
2. Click "Create Project"
3. Enter a project name (e.g., "IPEX Syndrome Research")
4. Add a description (optional)
5. Click "Create"

Your project is now ready! All your research data will be organized within this project.

### Understanding the Interface

The Drug Designer interface consists of:

- **Top Navigation**: Access different modules (Disease, Targets, Evidence, etc.)
- **Sidebar**: Quick access to recent projects and saved items
- **Main Content Area**: Where you'll interact with data and tools
- **Inspector Panel**: View provenance and diagnostic information

## Core Concepts

### Evidence-First Approach

Every claim in Drug Designer is backed by evidence from scientific sources:

- **Evidence Items**: Individual pieces of evidence from sources like PubMed, UniProt
- **Provenance**: Complete tracking of where data came from
- **Confidence Scores**: Quantitative assessment of evidence quality
- **Contradictions**: Automatic detection of conflicting evidence

### Provenance Tracking

All data includes provenance information:

- **Sources**: Which databases/APIs provided the data
- **Timestamps**: When the data was retrieved
- **Runtime Mode**: Whether data came from hosted or local inference
- **Model Versions**: Which AI models were used

### MAV Consensus

Multi-Agent Voting (MAV) ensures accuracy:

- **Jury of Specialists**: 3-7 AI agents review evidence
- **Voting**: Each agent votes "verified" or "contradicted"
- **Consensus**: Majority vote determines outcome
- **Truthful Pause**: Human review when no consensus is reached

## Module Guides

### Disease Intelligence

**Purpose**: Discover candidate genes and targets for a disease

#### Running a Disease Intelligence Query

1. Navigate to **Disease Intelligence**
2. Enter a disease name (e.g., "IPEX syndrome")
3. (Optional) Select specific data sources
4. (Optional) Enable Indian population context
5. Click "Search"

#### Understanding Results

The results include:

- **Normalized Disease Name**: Standardized disease label
- **Identifiers**: MONDO, OMIM, MeSH IDs
- **Candidate Genes**: Genes associated with the disease
- **Evidence**: Supporting evidence for each gene
- **Contradictions**: Any conflicting information

#### Example Workflow

```
1. Search "IPEX syndrome"
2. Review candidate genes (FOXP3, IL2RA, CD25)
3. Click on a gene to see detailed evidence
4. Save interesting genes to your project
5. Export results for further analysis
```

### Target Discovery

**Purpose**: Prioritize and rank therapeutic targets

#### Ranking Targets

1. Navigate to **Target Discovery**
2. Select candidate genes (from Disease Intelligence or manual entry)
3. Configure scoring weights:
   - GWAS associations
   - Druggability
   - Pathway centrality
   - Expression levels
   - Safety profile
   - Novelty
   - Literature support
4. Click "Rank Targets"

#### Understanding Scores

Each target receives:

- **Composite Score**: Overall ranking (0-1)
- **Score Breakdown**: Individual component scores
- **Evidence Breakdown**: Supporting evidence counts
- **Contradiction Flag**: Whether conflicting data exists

#### Example Workflow

```
1. Import genes from Disease Intelligence
2. Set high weight on druggability (0.3)
3. Set medium weight on safety (0.2)
4. Run ranking
5. Review top 10 targets
6. Export to dossier
```

### Clinical Workflow

**Purpose**: Process clinical data through a 10-stage pipeline

#### The 10-Stage Pipeline

1. **EHR Ingestion**: Import electronic health records
2. **Phenotype Clustering**: Group similar patient phenotypes
3. **Tissue Analysis**: Analyze histopathology images
4. **Biomarker Quantification**: Quantify flow cytometry data
5. **Genomic Sequencing**: Process VCF genomic data
6. **Pathogenicity Prediction**: Predict variant pathogenicity
7. **Knowledge Graph**: Cross-reference with biomedical databases
8. **Disruption Modeling**: Simulate mutation effects
9. **Drug Matching**: Match pathways to treatments
10. **Therapy Stratification**: Calculate therapy compatibility

#### Running a Clinical Workflow

1. Navigate to **Clinical Workflow**
2. Click "Start New Workflow"
3. Upload EHR data (HL7, FHIR, or CDA format)
4. Configure workflow settings
5. Click "Start Workflow"
6. Monitor progress in real-time (WebSocket updates)
7. Review results for each stage

#### PHI Protection

All clinical data is automatically protected:

- **Automatic PHI Detection**: Names, dates, locations, IDs
- **Redaction**: PHI is replaced with `[Filtered]`
- **Encryption**: All data encrypted at rest
- **Audit Logging**: Complete trail of all access
- **HIPAA Compliance**: Full compliance with HIPAA regulations

### Evidence Management

**Purpose**: Search, save, and organize scientific evidence

#### Searching Evidence

1. Navigate to **Evidence**
2. Enter search terms (e.g., "FOXP3 regulatory T cells")
3. Select sources (PubMed, UniProt, etc.)
4. Apply filters (date range, confidence threshold)
5. Click "Search"

#### Saving Evidence

1. Review search results
2. Click "Save" on relevant evidence items
3. Add tags for organization
4. Add notes (optional)
5. Evidence is saved to your project

#### Managing Contradictions

1. Navigate to **Evidence** → **Contradictions**
2. Review flagged contradictions
3. Click on a contradiction to see details
4. Mark as "Resolved" or "Needs Review"
5. Add resolution notes

### Dossier Generation

**Purpose**: Create comprehensive decision documents

#### Creating a Dossier

1. Navigate to **Dossiers**
2. Click "Create Dossier"
3. Enter dossier name and description
4. Add evidence items:
   - From saved evidence
   - From disease intelligence results
   - From target prioritization
5. Configure MAV consensus settings
6. Click "Generate Dossier"

#### Dossier Contents

A dossier includes:

- **Executive Summary**: High-level overview
- **Evidence Sections**: Organized by topic
- **MAV Consensus Results**: Verification status
- **Provenance Appendix**: Complete source tracking
- **Contradiction Report**: Any conflicting evidence

#### Exporting Dossiers

1. Open a dossier
2. Click "Export"
3. Select format:
   - **PDF**: Professional report with provenance
   - **DOCX**: Editable Microsoft Word document
   - **JSON**: Machine-readable format
4. Click "Download"

## Advanced Features

### Runtime Modes

Drug Designer supports three runtime modes:

1. **Hosted**: All inference runs on cloud servers (default)
2. **Local**: Inference runs on your local machine (requires local agent)
3. **Auto**: Automatically switches based on availability

#### Switching Runtime Modes

1. Navigate to **Runtime**
2. Select desired mode
3. Click "Apply"
4. (For Local mode) Follow instructions to install local agent

### Research Labs

Advanced computational labs for specialized analyses:

- **Pocket Detection**: Find binding pockets in protein structures
- **Molecule Generation**: Generate novel drug candidates
- **ADMET Prediction**: Predict absorption, distribution, metabolism, excretion, toxicity
- **Retrosynthesis**: Plan synthetic routes for molecules
- **Vaccine Design**: Design epitope-based vaccines (advanced)
- **Metabolic Engineering**: Optimize metabolic pathways (advanced)
- **Pharmacogenomics**: Predict drug response based on genetics (advanced)

Hosted release note:
`AutoDock Vina`, `fpocket`, and `P2Rank` are treated as optional local-native tools. If they are not installed in the active runtime, Drug Designer labels those actions as unavailable instead of presenting them as standard shipped capabilities.

### SynthArena

Compare competing scenarios side-by-side:

1. Navigate to **SynthArena**
2. Create a comparison session
3. Add 2-5 competing scenarios
4. Configure scoring criteria
5. Run comparison
6. Review results with uncertainty quantification

## Troubleshooting

### Common Issues

#### "No results found"

**Possible causes**:
- Disease name not recognized
- No data available in selected sources
- Network connectivity issues

**Solutions**:
- Try alternative disease names or synonyms
- Enable more data sources
- Check internet connection

#### "Circuit breaker open"

**Meaning**: An external data source is temporarily unavailable

**Solutions**:
- Wait 5 minutes for automatic recovery
- Disable the failing source
- Try again later

#### "PHI detected in logs"

**Meaning**: Potential PHI leakage detected

**Action**: Contact support immediately with error details

#### Slow performance

**Possible causes**:
- Large dataset
- Many concurrent users
- Network latency

**Solutions**:
- Reduce query scope
- Use filters to limit results
- Try during off-peak hours
- Consider local runtime mode

### Getting Help

- **Documentation**: https://docs.drugdesigner.com
- **Support Email**: support@drugdesigner.com
- **Status Page**: https://status.drugdesigner.com
- **Community Forum**: https://community.drugdesigner.com

## FAQ

### General

**Q: Is Drug Designer free?**  
A: Contact sales for pricing information.

**Q: Can I use Drug Designer offline?**  
A: Partial offline support with local runtime mode. Some features require internet connection.

**Q: How is my data protected?**  
A: All data is encrypted at rest and in transit. PHI is automatically redacted. Full HIPAA compliance.

### Disease Intelligence

**Q: How many data sources are available?**  
A: 140+ scientific databases and APIs across 9 families.

**Q: How long does a disease intelligence query take?**  
A: Typically 15-30 seconds, depending on query complexity.

**Q: Can I add custom data sources?**  
A: Contact support for custom integrations.

### Clinical Workflow

**Q: What EHR formats are supported?**  
A: HL7 v2/v3, FHIR R4, and CDA formats.

**Q: How long does the full 10-stage pipeline take?**  
A: Typically 20-30 minutes, depending on data size.

**Q: Is PHI automatically removed?**  
A: Yes, all PHI is automatically detected and redacted.

### Dossiers

**Q: How long does dossier generation take?**  
A: Typically 60-90 seconds, including MAV consensus.

**Q: Can I edit a generated dossier?**  
A: Yes, export as DOCX for editing in Microsoft Word.

**Q: What is MAV consensus?**  
A: Multi-Agent Voting where 3-7 AI specialists review evidence for accuracy.

### Performance

**Q: What are the SLA targets?**  
A: See [Performance SLA Documentation](../monitoring/METRICS.md) for detailed targets.

**Q: Why is my query slow?**  
A: Large datasets, many sources, or network latency. Try reducing scope or using filters.

**Q: Can I monitor system performance?**  
A: Yes, performance dashboards are available in the Runtime section.

## Next Steps

Now that you're familiar with Drug Designer:

1. **Complete the tutorial**: Follow the guided tutorial in the app
2. **Explore modules**: Try each module with sample data
3. **Join the community**: Connect with other researchers
4. **Read advanced guides**: Dive deeper into specific features
5. **Provide feedback**: Help us improve the platform

## Additional Resources

- **API Documentation**: [docs/api/README.md](../api/README.md)
- **Clinical Workflow Guide**: [docs/user-guide/clinical-workflow.md](clinical-workflow.md)
- **Monitoring Guide**: [docs/monitoring/README.md](../monitoring/README.md)
- **Video Tutorials**: https://tutorials.drugdesigner.com
- **Webinars**: https://webinars.drugdesigner.com

---

**Last Updated**: Task 17.2 Implementation  
**Version**: 1.0  
**Status**: Complete

**Need Help?** Contact support@drugdesigner.com
