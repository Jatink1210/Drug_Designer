/**
 * E2E tests for Target Prioritization workflow
 */

describe('Target Prioritization Workflow', () => {
  beforeEach(() => {
    // Login
    cy.visit('/login');
    cy.get('input[name="email"]').type('test@example.com');
    cy.get('input[name="password"]').type('SecurePassword123!');
    cy.get('button[type="submit"]').click();
    cy.url().should('include', '/dashboard');
  });

  it('should complete target prioritization workflow', () => {
    // Navigate to target prioritization
    cy.visit('/target-prioritization');
    cy.contains('Target Prioritization').should('be.visible');

    // Step 1: Enter disease
    cy.get('input[name="disease"]').type('IPEX syndrome');
    cy.get('button').contains('Discover Targets').click();

    // Wait for target discovery
    cy.get('[data-testid="target-list"]', { timeout: 15000 }).should('be.visible');
    cy.get('[data-testid="target-row"]').should('have.length.greaterThan', 0);

    // Step 2: Configure scoring criteria
    cy.get('button[data-testid="configure-scoring"]').click();
    cy.get('[data-testid="scoring-modal"]').should('be.visible');
    cy.get('input[name="druggability-weight"]').clear().type('0.3');
    cy.get('input[name="genetic-evidence-weight"]').clear().type('0.3');
    cy.get('input[name="expression-weight"]').clear().type('0.2');
    cy.get('input[name="safety-weight"]').clear().type('0.2');
    cy.get('button').contains('Apply').click();

    // Step 3: Score targets
    cy.get('button').contains('Score Targets').click();
    cy.get('[data-testid="scoring-progress"]', { timeout: 10000 }).should('be.visible');
    cy.get('[data-testid="scoring-complete"]', { timeout: 30000 }).should('be.visible');

    // Verify scores are displayed
    cy.get('[data-testid="target-score"]').should('have.length.greaterThan', 0);
    cy.get('[data-testid="target-row"]').first().should('contain', 'FOXP3');

    // Step 4: View target details
    cy.get('[data-testid="target-row"]').first().click();
    cy.get('[data-testid="target-details-modal"]').should('be.visible');
    cy.contains('Gene Symbol').should('be.visible');
    cy.contains('Druggability Score').should('be.visible');

    // Step 5: View protein structure
    cy.get('button').contains('View Structure').click();
    cy.get('[data-testid="structure-viewer"]', { timeout: 10000 }).should('be.visible');
  });

  it('should filter and sort targets', () => {
    cy.visit('/target-prioritization');
    cy.get('input[name="disease"]').type('IPEX syndrome');
    cy.get('button').contains('Discover Targets').click();
    cy.get('[data-testid="target-list"]', { timeout: 15000 }).should('be.visible');

    // Apply filters
    cy.get('button[data-testid="filter-button"]').click();
    cy.get('select[name="target-class"]').select('kinase');
    cy.get('input[name="druggability-min"]').type('0.5');
    cy.get('button').contains('Apply Filters').click();

    // Verify filtered results
    cy.get('[data-testid="target-row"]').should('have.length.greaterThan', 0);

    // Sort by score
    cy.get('th').contains('Priority Score').click();
    cy.get('[data-testid="target-row"]').first().should('have.attr', 'data-rank', '1');
  });

  it('should compare multiple targets', () => {
    cy.visit('/target-prioritization');
    cy.get('input[name="disease"]').type('IPEX syndrome');
    cy.get('button').contains('Discover Targets').click();
    cy.get('[data-testid="target-list"]', { timeout: 15000 }).should('be.visible');

    // Select multiple targets
    cy.get('[data-testid="target-checkbox"]').eq(0).check();
    cy.get('[data-testid="target-checkbox"]').eq(1).check();
    cy.get('[data-testid="target-checkbox"]').eq(2).check();

    // Compare
    cy.get('button').contains('Compare Selected').click();
    cy.get('[data-testid="comparison-modal"]').should('be.visible');
    cy.get('[data-testid="comparison-table"]').should('be.visible');
    cy.get('[data-testid="comparison-row"]').should('have.length', 3);
  });

  it('should export target prioritization results', () => {
    cy.visit('/target-prioritization');
    cy.get('input[name="disease"]').type('IPEX syndrome');
    cy.get('button').contains('Discover Targets').click();
    cy.get('[data-testid="target-list"]', { timeout: 15000 }).should('be.visible');

    // Export
    cy.get('button[data-testid="export-button"]').click();
    cy.get('[data-testid="export-modal"]').should('be.visible');
    cy.get('select[name="format"]').select('CSV');
    cy.get('button').contains('Export').click();

    // Verify download
    cy.get('[data-testid="export-success"]', { timeout: 10000 }).should('be.visible');
  });

  it('should validate target with evidence', () => {
    cy.visit('/target-prioritization');
    cy.get('input[name="disease"]').type('IPEX syndrome');
    cy.get('button').contains('Discover Targets').click();
    cy.get('[data-testid="target-list"]', { timeout: 15000 }).should('be.visible');

    // Select target
    cy.get('[data-testid="target-row"]').first().click();
    cy.get('[data-testid="target-details-modal"]').should('be.visible');

    // Validate target
    cy.get('button').contains('Validate Target').click();
    cy.get('[data-testid="validation-modal"]').should('be.visible');
    cy.get('input[name="genetic-evidence"]').check();
    cy.get('input[name="expression-data"]').check();
    cy.get('input[name="pathway-analysis"]').check();
    cy.get('button').contains('Run Validation').click();

    // Wait for validation
    cy.get('[data-testid="validation-results"]', { timeout: 20000 }).should('be.visible');
    cy.get('[data-testid="validation-score"]').should('be.visible');
  });

  it('should handle pagination', () => {
    cy.visit('/target-prioritization');
    cy.get('input[name="disease"]').type('syndrome');
    cy.get('button').contains('Discover Targets').click();
    cy.get('[data-testid="target-list"]', { timeout: 15000 }).should('be.visible');

    // Check pagination controls
    cy.get('[data-testid="pagination"]').should('be.visible');
    cy.get('button[data-testid="next-page"]').click();
    cy.get('[data-testid="page-number"]').should('contain', '2');
  });
});
