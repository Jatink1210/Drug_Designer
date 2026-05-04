# E2E Tests with Cypress

End-to-end tests for Drug Designer platform using Cypress.

## Test Coverage

### Clinical Workflow Tests (`clinical_workflow.cy.ts`)
- **Stage 1**: EHR Data Ingestion
- **Stage 2**: AI Phenotype Clustering
- **Stage 3**: DL Tissue Analysis
- **Stage 4**: Neural Network Biomarker Quantification
- **Stage 5**: Genomic Sequencing (VCF)
- **Stage 6**: DL Pathogenicity Prediction
- **Stage 8**: AI Disruption Modeling
- **Stage 9**: AI Targeted Drug Matching
- **Stage 10**: Advanced Therapy Stratification
- **Complete Workflow Integration**
- **WebSocket Progress Updates**
- **PHI Protection**

### User Journey Tests (`user_journeys.cy.ts`)
- **Journey 1**: Disease Intelligence
- **Journey 2**: Target Discovery & Prioritization
- **Journey 3**: Dossier Generation
- **Journey 4**: Project Management
- **Journey 5**: Evidence Management
- **Authentication & Authorization**
- **Error Handling**
- **Performance**

## Running Tests

### Prerequisites:
```bash
# Install dependencies
cd apps/web
npm install

# Start application
npm run dev

# Start API server
cd apps/api
python run_server.py
```

### Run all E2E tests:
```bash
cd apps/web
npx cypress run
```

### Open Cypress Test Runner:
```bash
npx cypress open
```

### Run specific test file:
```bash
npx cypress run --spec "cypress/e2e/clinical_workflow.cy.ts"
```

### Run in headless mode:
```bash
npx cypress run --headless
```

### Run with specific browser:
```bash
npx cypress run --browser chrome
npx cypress run --browser firefox
npx cypress run --browser edge
```

## Test Configuration

Configuration is in `cypress.config.ts`:
- **Base URL**: http://localhost:3000
- **Viewport**: 1280x720
- **Default Timeout**: 10 seconds
- **Request Timeout**: 30 seconds
- **Page Load Timeout**: 60 seconds
- **Retries**: 2 (run mode), 0 (open mode)

## Custom Commands

Custom commands are defined in `cypress/support/commands.ts`:

### Login
```typescript
cy.login('test@example.com', 'password');
```

### Create Project
```typescript
cy.createProject('Test Project', 'Description').then((projectId) => {
  // Use project ID
});
```

### Wait for API
```typescript
cy.intercept('POST', '/api/v1/disease/search').as('searchDisease');
cy.waitForApi('@searchDisease');
```

## Test Fixtures

Test fixtures are in `cypress/fixtures/`:
- `sample_ehr.hl7` - Sample EHR data
- `sample_wsi.tiff` - Sample tissue image
- `sample_flow_cytometry.fcs` - Sample flow cytometry data
- `sample.vcf` - Sample VCF file

## Best Practices

1. **Use data-testid attributes** - For stable selectors
2. **Wait for elements** - Use `cy.contains()` with timeout
3. **Intercept API calls** - Mock or spy on API requests
4. **Clean up after tests** - Reset state between tests
5. **Use custom commands** - For repeated actions
6. **Handle async operations** - Use proper waits
7. **Test error states** - Verify error handling
8. **Test accessibility** - Use semantic selectors

## Debugging

### View test videos:
```bash
open cypress/videos/
```

### View screenshots:
```bash
open cypress/screenshots/
```

### Debug in browser:
```bash
npx cypress open
# Click on test file
# Use browser DevTools
```

### Add debug points:
```typescript
cy.debug();
cy.pause();
```

## CI/CD Integration

E2E tests run in CI/CD pipeline:
```yaml
# .github/workflows/e2e.yml
- name: Run E2E tests
  run: |
    npm run dev &
    npx wait-on http://localhost:3000
    npx cypress run
```

## Performance Requirements

- **Clinical Workflow**: Complete in <10 minutes
- **User Journeys**: Each journey <2 minutes
- **Page Load**: <3 seconds
- **API Response**: <30 seconds

## Troubleshooting

### Tests timing out:
- Increase timeout in `cypress.config.ts`
- Check if application is running
- Check API server is running

### Element not found:
- Use `cy.get('[data-testid="element"]', { timeout: 10000 })`
- Check if element exists in DOM
- Use Cypress Test Runner to inspect

### API errors:
- Check API server logs
- Verify API endpoints
- Check authentication

### WebSocket errors:
- Verify WebSocket connection
- Check WebSocket server
- Monitor browser console

## Related Documentation

- [Unit Tests](../src/tests/README.md)
- [Integration Tests](../../api/tests/integration/README.md)
- [Cypress Documentation](https://docs.cypress.io)
