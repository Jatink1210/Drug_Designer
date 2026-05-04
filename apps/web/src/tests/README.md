# Frontend Unit Tests

Comprehensive unit test suite for Drug Designer frontend components.

## Test Coverage

### UI Components
- **Button** (`Button.test.tsx`)
  - Rendering with text
  - Click event handling
  - Variant styles (primary, secondary)
  - Disabled state
  - Loading state
  - Icon support

- **Card** (`Card.test.tsx`)
  - Rendering with children
  - Title, header, footer
  - Hover effects
  - Loading state
  - Empty state

- **LanguageSwitcher** (`LanguageSwitcher.test.tsx`)
  - Language display
  - Language options
  - Language switching
  - Dropdown behavior

### Page Components
- Disease Intelligence pages
- Target Discovery pages
- Evidence pages
- Clinical Workflow pages
- Labs pages
- Reports/Dossiers pages

### Hooks & Utilities
- Custom hooks
- API utilities
- State management
- Form validation

## Running Tests

### Run all tests:
```bash
cd apps/web
npm test
```

### Run specific test file:
```bash
npm test Button.test.tsx
```

### Run with coverage:
```bash
npm test -- --coverage
```

### Run in watch mode:
```bash
npm test -- --watch
```

### Run tests matching pattern:
```bash
npm test -- -t "Button"
```

## Test Structure

```
apps/web/src/
├── components/
│   ├── ui/
│   │   ├── Button.test.tsx
│   │   ├── Card.test.tsx
│   │   └── Navigation.test.tsx
│   └── LanguageSwitcher.test.tsx
├── pages/
│   ├── DiseaseIntelligence.test.tsx
│   └── TargetDiscovery.test.tsx
├── hooks/
│   └── useApi.test.ts
├── utils/
│   └── api.test.ts
├── setupTests.ts
└── tests/
    └── README.md
```

## Mocking Strategy

Tests use extensive mocking to:
- Mock API calls with `jest.fn()`
- Mock React Router navigation
- Mock i18n translations
- Mock WebSocket connections
- Provide deterministic results

## Coverage Goals

- **Overall**: >70% code coverage
- **Components**: >80% coverage
- **Utilities**: >90% coverage
- **Hooks**: >75% coverage

## Performance Requirements

- **Total execution time**: <2 minutes
- **Individual test**: <100ms
- **Parallel execution**: Supported

## Best Practices

1. **Use React Testing Library** - Test user behavior, not implementation
2. **Mock external dependencies** - No real API calls
3. **Test accessibility** - Use semantic queries
4. **Test error states** - Verify error handling
5. **Keep tests fast** - Use mocks, avoid timeouts
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
- Maintain >70% coverage
- Fix failing tests immediately
- Review coverage reports regularly
- Update mocks when APIs change

## Related Documentation

- [Backend Unit Tests](../../api/tests/unit/README.md)
- [Integration Tests](../integration/README.md)
- [E2E Tests](../e2e/README.md)
