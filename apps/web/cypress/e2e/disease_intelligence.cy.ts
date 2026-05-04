/**
 * E2E tests for Disease Intelligence workflow
 */

describe('Disease Intelligence Workflow', () => {
  beforeEach(() => {
    // Login before each test
    cy.visit('/login');
    cy.get('input[name="email"]').type('test@example.com');
    cy.get('input[name="password"]').type('SecurePassword123!');
    cy.get('button[type="submit"]').click();
    cy.url().should('include', '/dashboard');
  });

  it('should complete disease intelligence workflow', () => {
    // Navigate to disease intelligence
    cy.visit('/disease-intelligence');
    cy.contains('Disease Intelligence').should('be.visible');

    // Step 1: Search for disease
    cy.get('input[placeholder*="Search"]').type('IPEX syndrome');
    cy.get('button').contains('Search').click();

    // Wait for results
    cy.get('[data-testid="disease-results"]', { timeout: 10000 }).should('be.visible');
    cy.get('[data-testid="disease-card"]').should('have.length.greaterThan', 0);

    // Select first disease
    cy.get('[data-testid="disease-card"]').first().click();

    // Step 2: View disease details
    cy.url().should('include', '/disease/');
    cy.contains('IPEX').should('be.visible');
    cy.get('[data-testid="disease-description"]').should('be.visible');

    // Step 3: Discover targets
    cy.get('button').contains('Discover Targets').click();
    cy.get('[data-testid="target-discovery-modal"]', { timeout: 10000 }).should('be.visible');
    cy.get('button').contains('Start Discovery').click();

    // Wait for target discovery
    cy.get('[data-testid="target-results"]', { timeout: 15000 }).should('be.visible');
    cy.get('[data-testid="target-card"]').should('have.length.greaterThan', 0);

    // Verify FOXP3 is in results
    cy.contains('FOXP3').should('be.visible');

    // Step 4: Search for evidence
    cy.get('button').contains('Search Evidence').click();
    cy.get('[data-testid="evidence-search-modal"]').should('be.visible');
    cy.get('input[name="query"]').type('FOXP3 mutations');
    cy.get('button').contains('Search').click();

    // Wait for evidence results
    cy.get('[data-testid="evidence-results"]', { timeout: 10000 }).should('be.visible');
    cy.get('[data-testid="evidence-item"]').should('have.length.greaterThan', 0);

    // Step 5: Build knowledge graph
    cy.get('button').contains('Build Knowledge Graph').click();
    cy.get('[data-testid="knowledge-graph"]', { timeout: 15000 }).should('be.visible');
    cy.get('[data-testid="graph-node"]').should('have.length.greaterThan', 0);
    cy.get('[data-testid="graph-edge"]').should('have.length.greaterThan', 0);
  });

  it('should filter disease search results', () => {
    cy.visit('/disease-intelligence');

    // Search with filters
    cy.get('input[placeholder*="Search"]').type('syndrome');
    cy.get('button[data-testid="filter-button"]').click();
    cy.get('select[name="category"]').select('genetic');
    cy.get('select[name="prevalence"]').select('rare');
    cy.get('button').contains('Apply Filters').click();

    // Verify filtered results
    cy.get('[data-testid="disease-results"]', { timeout: 10000 }).should('be.visible');
    cy.get('[data-testid="disease-card"]').should('have.length.greaterThan', 0);
  });

  it('should export disease intelligence report', () => {
    cy.visit('/disease-intelligence');
    cy.get('input[placeholder*="Search"]').type('IPEX syndrome');
    cy.get('button').contains('Search').click();
    cy.get('[data-testid="disease-card"]').first().click();

    // Export report
    cy.get('button[data-testid="export-button"]').click();
    cy.get('[data-testid="export-modal"]').should('be.visible');
    cy.get('select[name="format"]').select('PDF');
    cy.get('button').contains('Export').click();

    // Verify download initiated
    cy.get('[data-testid="export-success"]', { timeout: 10000 }).should('be.visible');
  });

  it('should save disease intelligence workflow', () => {
    cy.visit('/disease-intelligence');
    cy.get('input[placeholder*="Search"]').type('IPEX syndrome');
    cy.get('button').contains('Search').click();
    cy.get('[data-testid="disease-card"]').first().click();

    // Save workflow
    cy.get('button[data-testid="save-workflow"]').click();
    cy.get('input[name="workflow-name"]').type('IPEX Investigation');
    cy.get('button').contains('Save').click();

    // Verify saved
    cy.get('[data-testid="save-success"]').should('be.visible');

    // Navigate to saved workflows
    cy.visit('/workflows');
    cy.contains('IPEX Investigation').should('be.visible');
  });

  it('should handle errors gracefully', () => {
    cy.visit('/disease-intelligence');

    // Search with invalid query
    cy.get('input[placeholder*="Search"]').type('');
    cy.get('button').contains('Search').click();

    // Verify error message
    cy.get('[data-testid="error-message"]').should('be.visible');
    cy.contains('Please enter a search query').should('be.visible');
  });
});
