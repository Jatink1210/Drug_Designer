# API Integration Tests

Integration tests for Drug Designer API endpoints with real database connections.

## Test Coverage

### Health Endpoints
- Health check
- Readiness check

### Project Management
- Create project
- List projects
- Get project
- Update project
- Delete project

### Clinical Workflow
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
- Multi-agent voting
- Consensus retrieval
- Truthful pause handling

### Export Services
- PDF export
- DOCX export
- SDF export
- Bulk export

### Authentication
- User login
- Token validation
- Unauthorized access

### Error Handling
- 404 errors
- Invalid JSON
- Validation errors
- Rate limiting

## Running Tests

### Prerequisites:
```bash
# Start test database
docker-compose -f docker-compose.test.yml up -d postgres

# Run migrations
cd apps/api
alembic upgrade head
```

### Run all integration tests:
```bash
cd apps/api
pytest tests/integration/ -v
```

### Run specific test file:
```bash
pytest tests/integration/test_api_endpoints.py -v
```

### Run with coverage:
```bash
pytest tests/integration/ --cov=. --cov-report=html
```

### Run tests matching pattern:
```bash
pytest tests/integration/ -k "test_project" -v
```

## Test Database

Integration tests use a separate test database:
- **Database**: `drugdesigner_test`
- **User**: `test`
- **Password**: `test`
- **Host**: `localhost`
- **Port**: `5432`

The test database is created and destroyed for each test function to ensure isolation.

## Test Structure

```
tests/integration/
├── __init__.py
├── README.md
├── test_api_endpoints.py       # API endpoint tests
├── test_database.py            # Database operation tests
├── conftest.py                 # Shared fixtures
└── docker-compose.test.yml     # Test database setup
```

## Fixtures

- `test_db` - Creates/drops test database tables
- `db_session` - Provides database session
- `client` - FastAPI test client
- `auth_headers` - Authentication headers

## Best Practices

1. **Use test database** - Never run tests against production
2. **Clean up after tests** - Drop tables after each test
3. **Test real scenarios** - Use actual database operations
4. **Test error paths** - Verify error handling
5. **Test authentication** - Verify access control
6. **Test rate limiting** - Verify rate limits work
7. **Use transactions** - Rollback after each test
8. **Mock external APIs** - Don't call real external services

## Performance Requirements

- **Total execution time**: <5 minutes
- **Individual test**: <5 seconds
- **Database setup/teardown**: <1 second

## CI/CD Integration

These integration tests run:
- On pull requests
- Before deployment
- Nightly builds
- After database migrations

## Troubleshooting

### Database connection errors:
```bash
# Check if test database is running
docker ps | grep postgres

# Check database logs
docker logs drugdesigner_test_db
```

### Migration errors:
```bash
# Reset test database
docker-compose -f docker-compose.test.yml down -v
docker-compose -f docker-compose.test.yml up -d
alembic upgrade head
```

### Test failures:
```bash
# Run with verbose output
pytest tests/integration/ -vv

# Run with debugging
pytest tests/integration/ --pdb
```

## Related Documentation

- [Unit Tests](../unit/README.md)
- [E2E Tests](../../web/cypress/README.md)
- [API Documentation](../../docs/api/README.md)
