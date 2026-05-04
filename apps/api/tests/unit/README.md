# Backend Unit Tests

Comprehensive unit test suite for Drug Designer backend services.

## Test Coverage

### Core Utilities (>80% coverage target)
- **PHI Protection** (`test_phi_protection.py`)
  - PHI detection (SSN, phone, email, dates, MRN, IP addresses)
  - Redaction functionality
  - HIPAA compliance validation
  - Dictionary scanning

- **Circuit Breaker** (`test_circuit_breaker.py`)
  - State transitions (CLOSED → OPEN → HALF_OPEN)
  - Failure threshold detection
  - Recovery timeout handling
  - Per-connector isolation

- **Rate Limiter** (`test_rate_limiter.py`)
  - Token bucket algorithm
  - Burst handling
  - Retry-after support
  - Per-connector rate limits

- **WebSocket Manager** (`test_websocket_manager.py`)
  - Connection management
  - Event emission
  - Clinical workflow events
  - Message routing

### Clinical Workflow Services
- **Clinical Services** (`test_clinical_services.py`)
  - EHR data ingestion
  - Phenotype clustering
  - Tissue analysis
  - Biomarker quantification
  - Genomic sequencing
  - Pathogenicity prediction
  - Disruption modeling
  - Drug matching
  - Therapy stratification

### MAV Consensus
- **MAV Consensus** (`test_mav_consensus.py`)
  - Multi-agent voting
  - Specialist assignment
  - Vote aggregation
  - Truthful pause triggering
  - Consensus trace logging

### Export Services
- **Export Services** (`test_export_services.py`)
  - PDF export (with provenance)
  - DOCX export
  - SDF export
  - Bulk project export
  - Export metadata tracking

### Deep Learning Models
- **ML Models** (`test_ml_models.py`)
  - ESM-2 protein embeddings
  - MolFormer molecule embeddings
  - R-GCN graph reasoning
  - GAT target ranking
  - Tissue analysis CV model
  - Biomarker quantification NN
  - Pathogenicity prediction DL
  - Disruption simulator
  - Drug matching recommender

### Connectors
- **Connectors** (`test_connectors.py`)
  - Base connector framework
  - Circuit breaker integration
  - Rate limiting integration
  - Sample connector implementations (PubMed, UniProt, ChEMBL)
  - Health monitoring
  - Retry logic
  - Response caching

## Running Tests

### Run all unit tests:
```bash
cd apps/api
pytest tests/unit/ -v
```

### Run specific test file:
```bash
pytest tests/unit/test_phi_protection.py -v
```

### Run with coverage:
```bash
pytest tests/unit/ --cov=. --cov-report=html
```

### Run tests matching pattern:
```bash
pytest tests/unit/ -k "test_phi" -v
```

### Run tests in parallel:
```bash
pytest tests/unit/ -n auto
```

## Test Structure

```
tests/unit/
├── __init__.py
├── conftest.py                    # Shared fixtures
├── README.md                      # This file
├── test_phi_protection.py         # PHI detection & redaction
├── test_circuit_breaker.py        # Circuit breaker
├── test_rate_limiter.py           # Rate limiting
├── test_websocket_manager.py      # WebSocket management
├── test_clinical_services.py      # Clinical workflows
├── test_mav_consensus.py          # MAV consensus
├── test_export_services.py        # Export services
├── test_ml_models.py              # Deep learning models
└── test_connectors.py             # Connector framework
```

## Fixtures (conftest.py)

- `mock_db_session` - Mock database session
- `mock_redis` - Mock Redis client
- `mock_qdrant` - Mock Qdrant vector store
- `mock_neo4j` - Mock Neo4j graph database
- `sample_user_id` - Sample user UUID
- `sample_project_id` - Sample project UUID
- `sample_run_id` - Sample run UUID
- `mock_llm_response` - Mock LLM response
- `mock_http_client` - Mock HTTP client

## Mocking Strategy

Tests use extensive mocking to:
- Avoid external API calls
- Eliminate database dependencies
- Ensure fast execution (<5 minutes total)
- Enable parallel test execution
- Provide deterministic results

## Coverage Goals

- **Overall**: >80% code coverage
- **Critical paths**: 100% coverage
- **Core utilities**: >90% coverage
- **Services**: >80% coverage
- **Models**: >70% coverage (interface testing)

## Performance Requirements

- **Total execution time**: <5 minutes
- **Individual test**: <1 second
- **Async tests**: <100ms (mocked)
- **Parallel execution**: Supported

## Best Practices

1. **Use mocks extensively** - No real external calls
2. **Test interfaces** - Focus on public APIs
3. **Test error paths** - Verify error handling
4. **Test edge cases** - Boundary conditions
5. **Keep tests fast** - Use mocks, avoid I/O
6. **Make tests independent** - No shared state
7. **Use descriptive names** - Clear test intent
8. **Follow AAA pattern** - Arrange, Act, Assert

## Integration with CI/CD

These unit tests run on every commit:
- Pre-commit hooks
- Pull request validation
- CI/CD pipeline
- Coverage reporting

## Maintenance

- Update tests when adding new features
- Maintain >80% coverage
- Fix failing tests immediately
- Review coverage reports regularly
- Update mocks when APIs change

## Related Documentation

- [Audit Logging Tests](../test_audit_logging.py)
- [Clinical WebSocket Tests](../test_clinical_websocket.py)
- [Design Document](../../.kiro/specs/drug-designer-codebase-alignment/design.md)
- [Requirements Document](../../.kiro/specs/drug-designer-codebase-alignment/requirements.md)
