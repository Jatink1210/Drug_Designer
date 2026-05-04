# Connector Unit Tests

This directory contains comprehensive unit tests for all 87+ Drug Designer connectors.

## Overview

**Test Coverage:** 120+ connector test files
**Target Coverage:** >80% code coverage for all connectors
**Test Categories:**
- Mock external API calls
- Error handling (network errors, invalid responses, timeouts)
- Rate limiting enforcement
- Circuit breaker behavior
- Caching mechanisms
- Provenance tracking
- Data normalization

## Structure

```
tests/unit/connectors/
├── conftest.py                      # Shared fixtures and pytest configuration
├── test_base_connector.py           # Tests for BaseConnector functionality
├── test_connector_template.py       # Template connector tests
├── generate_connector_tests.py      # Test generator script
├── test_*_connector.py              # Individual connector tests (120 files)
└── README.md                        # This file
```

## Test Categories by Connector Family

### Literature Connectors (15)
- PubMed, Europe PMC, BioRxiv, MedRxiv, arXiv q-bio
- Crossref, Semantic Scholar, OpenAlex, Google Scholar
- SSRN, Patents, JSTOR, PLoS, Wiley, Nature

### Disease & Ontology Connectors (16)
- Disease Ontology, DisGeNET, OMIM, Orphanet, HPO
- MedGen, Monarch, ClinGen, GARD, GTR, MedDRA
- EFO, ICD-10, MeSH, SNOMED CT, UMLS

### Target & Protein Connectors (20)
- UniProt, AlphaFold, RCSB PDB, InterPro, Pharos
- BioGRID, IntAct, STRING, Human Protein Atlas
- ProteomicsDB, PeptideAtlas, PRIDE, PhosphoSitePlus
- dbPTM, PDB Europe, wwPDB, CATH, SCOP, Pfam, SMART

### Pathway & Interaction Connectors (9)
- Reactome, KEGG, WikiPathways, ConsensusPathDB
- PathwayNet, SIGNOR, NetPath, PID, PANTHER

### Compound & Drug Connectors (21)
- ChEMBL, PubChem, DrugBank, DrugCentral, Drugs@FDA
- EMA, CDSCO, PMDA, RxNorm, ATC, ChEBI
- BindingDB, ChEMBL Targets, ChemSpider, ZINC
- PDB Ligand, STITCH, DGIdb, SIDER, TTD, SuperDrug2

### Genetics & Variant Connectors (31)
- dbSNP, ClinVar, gnomAD, GWAS Catalog, Ensembl
- dbVar, UK Biobank, All of Us, TOPMed, PAGE
- BioBank Japan, China Kadoorie, GenomeAsia, IndiGen, IGVDB
- Open Targets, 1000 Genomes, ExAC, EVA, COSMIC
- ICGC, cBioPortal, TCGA, GTEx, HapMap, ALFA
- HGMD, LOVD, PharmGKB, PharmVar, DECIPHER

### Clinical & Translational Connectors (8)
- ClinicalTrials.gov, EU Clinical Trials, ISRCTN, WHO ICTRP
- AACT, ICTRP, CTRI, ANZCTR

## Running Tests

### Run All Connector Tests
```bash
pytest tests/unit/connectors/ -v
```

### Run Specific Connector Test
```bash
pytest tests/unit/connectors/test_pubmed_connector.py -v
```

### Run Tests by Category (using markers)
```bash
# Run only connector tests
pytest -m connector -v

# Run only unit tests
pytest -m unit -v

# Exclude slow tests
pytest -m "not slow" -v
```

### Run with Coverage Report
```bash
# Generate HTML coverage report
pytest tests/unit/connectors/ --cov=apps/api/connectors --cov-report=html

# Generate terminal coverage report
pytest tests/unit/connectors/ --cov=apps/api/connectors --cov-report=term-missing

# Target: >80% coverage for all connectors
```

### Run Parallel Tests (faster)
```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel
pytest tests/unit/connectors/ -n auto -v
```

### Run Specific Test Methods
```bash
# Run only rate limiting tests
pytest tests/unit/connectors/ -k "rate_limiting" -v

# Run only error handling tests
pytest tests/unit/connectors/ -k "error_handling" -v

# Run only caching tests
pytest tests/unit/connectors/ -k "caching" -v
```

## Test Structure

Each connector test file includes the following test methods:

### Core Functionality Tests
- `test_initialization` - Verify connector setup
- `test_search_success` - Test successful search operation
- `test_search_empty_results` - Test handling of no results
- `test_search_with_limit` - Test limit parameter
- `test_fetch_by_id_success` - Test entity retrieval by ID
- `test_fetch_by_id_not_found` - Test handling of missing entities

### Caching Tests
- `test_caching_behavior` - Verify caching works correctly

### Rate Limiting Tests
- `test_rate_limiting` - Verify rate limiting is enforced

### Error Handling Tests
- `test_error_handling_network_error` - Test network failure handling
- `test_error_handling_invalid_response` - Test malformed response handling
- `test_timeout_handling` - Test request timeout handling

### Circuit Breaker Tests
- `test_circuit_breaker_behavior` - Test circuit breaker opens after failures

### Provenance Tests
- `test_provenance_tracking` - Verify provenance metadata is tracked

### Additional Tests
- `test_count_method` - Test count functionality (if implemented)
- `test_extract_evidence` - Test evidence extraction (if implemented)
- `test_normalize_method` - Test data normalization
- `test_close_method` - Test connector cleanup

## Fixtures

Shared fixtures are defined in `conftest.py`:

- `mock_response` - Mock successful HTTP response
- `mock_error_response` - Mock error HTTP response
- `mock_rate_limit_response` - Mock rate limit response
- `sample_article_data` - Sample literature data
- `sample_protein_data` - Sample protein data
- `sample_compound_data` - Sample compound data
- `sample_clinical_trial_data` - Sample clinical trial data
- `sample_variant_data` - Sample genetic variant data

## Generating New Tests

To generate tests for new connectors:

1. Add connector metadata to `generate_connector_tests.py`
2. Run the generator:
   ```bash
   python tests/unit/connectors/generate_connector_tests.py
   ```

## Coverage Goals

**Target:** >80% code coverage for all connectors

**Current Status:**
- Base connector: ~90% coverage
- Individual connectors: Target >80% coverage
- Overall connector module: Target >80% coverage

## Continuous Integration

These tests are run automatically in CI/CD pipeline:
- On every pull request
- On every commit to main branch
- Nightly full test suite runs

## Troubleshooting

### Tests Failing Due to Async
Make sure to use `@pytest.mark.asyncio` decorator for async tests.

### Import Errors
Ensure `sys.path.insert(0, 'apps/api')` is present in test files.

### Mock Not Working
Use `AsyncMock` for async methods, `Mock` for sync methods.

### Rate Limiting Tests Slow
Use `pytest -m "not slow"` to skip slow tests during development.

## Contributing

When adding new connector tests:
1. Follow the existing test structure
2. Include all test categories (caching, rate limiting, error handling, etc.)
3. Mock all external API calls
4. Aim for >80% code coverage
5. Add appropriate markers (@pytest.mark.asyncio, @pytest.mark.slow, etc.)
6. Update this README if adding new test categories

## References

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [Drug Designer Connector Specification](../../../Drug_Designer.md)
