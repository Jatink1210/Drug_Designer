/**
 * E2E tests for Dossier Generation workflow
 */

describe('Dossier Generation Workflow', () => {
  beforeEach(() => {
    // Login
    cy.visit('/login');
    cy.get('input[name="email"]').type('test@example.com');
    cy.get('input[name="password"]').type('SecurePassword123!');
    cy.get('button[type="submit"]').click();
    cy.url().should('include', '/dashboard');
  });

  it('should generate complete dossier', () => {
    // Navigate to dossier generation
    cy.visit('/dossier');
    cy.contains('Dossier Generation').should('be.visible');

    // Step 1: Select project
    cy.get('select[name="project"]').select('IPEX Drug Discovery');
    cy.get('button').contains('Next').click();

    // Step 2: Configure dossier sections
    cy.get('[data-testid="section-selector"]').should('be.visible');
    cy.get('input[name="executive-summary"]').check();
    cy.get('input[name="disease-background"]').check();
    cy.get('input[name="target-analysis"]').check();
    cy.get('input[name="evidence-summary"]').check();
    cy.get('input[name="mav-consensus"]').check();
    cy.get('input[name="provenance"]').check();
    cy.get('button').contains('Next').click();

    // Step 3: Configure format options
    cy.get('[data-testid="format-options"]').should('be.visible');
    cy.get('input[name="include-toc"]').check();
    cy.get('input[name="include-appendix"]').check();
    cy.get('input[name="include-references"]').check();
    cy.get('select[name="citation-style"]').select('APA');
    cy.get('button').contains('Generate').click();

    // Wait for generation
    cy.get('[data-testid="generation-progress"]', { timeout: 10000 }).should('be.visible');
    cy.get('[data-testid="progress-bar"]').should('be.visible');

    // Wait for completion
    cy.get('[data-testid="generation-complete"]', { timeout: 90000 }).should('be.visible');
    cy.contains('Dossier generated successfully').should('be.visible');

    // Step 4: Preview dossier
    cy.get('button').contains('Preview').click();
    cy.get('[data-testid="dossier-preview"]').should('be.visible');
    cy.get('[data-testid="preview-page"]').should('have.length.greaterThan', 0);

    // Step 5: Download dossier
    cy.get('button').contains('Download PDF').click();
    cy.get('[data-testid="download-success"]', { timeout: 10000 }).should('be.visible');
  });

  it('should generate dossier with custom template', () => {
    cy.visit('/dossier');

    // Select custom template
    cy.get('select[name="project"]').select('IPEX Drug Discovery');
    cy.get('button[data-testid="use-template"]').click();
    cy.get('[data-testid="template-modal"]').should('be.visible');
    cy.get('[data-testid="template-card"]').contains('Regulatory Submission').click();
    cy.get('button').contains('Use Template').click();

    // Verify template sections are pre-selected
    cy.get('input[name="regulatory-summary"]').should('be.checked');
    cy.get('input[name="safety-data"]').should('be.checked');
    cy.get('input[name="efficacy-data"]').should('be.checked');

    // Generate
    cy.get('button').contains('Generate').click();
    cy.get('[data-testid="generation-complete"]', { timeout: 90000 }).should('be.visible');
  });

  it('should edit dossier sections', () => {
    cy.visit('/dossier');
    cy.get('select[name="project"]').select('IPEX Drug Discovery');
    cy.get('button').contains('Next').click();

    // Select sections
    cy.get('input[name="executive-summary"]').check();
    cy.get('button').contains('Next').click();

    // Generate
    cy.get('button').contains('Generate').click();
    cy.get('[data-testid="generation-complete"]', { timeout: 90000 }).should('be.visible');

    // Edit section
    cy.get('button').contains('Edit').click();
    cy.get('[data-testid="editor"]').should('be.visible');
    cy.get('[data-testid="section-executive-summary"]').click();
    cy.get('textarea[name="section-content"]').clear().type('Updated executive summary content');
    cy.get('button').contains('Save Changes').click();

    // Verify changes saved
    cy.get('[data-testid="save-success"]').should('be.visible');
  });

  it('should export dossier in multiple formats', () => {
    cy.visit('/dossier');
    cy.get('select[name="project"]').select('IPEX Drug Discovery');
    cy.get('button').contains('Next').click();
    cy.get('input[name="executive-summary"]').check();
    cy.get('button').contains('Next').click();
    cy.get('button').contains('Generate').click();
    cy.get('[data-testid="generation-complete"]', { timeout: 90000 }).should('be.visible');

    // Export as PDF
    cy.get('button[data-testid="export-dropdown"]').click();
    cy.get('[data-testid="export-pdf"]').click();
    cy.get('[data-testid="download-success"]', { timeout: 10000 }).should('be.visible');

    // Export as DOCX
    cy.get('button[data-testid="export-dropdown"]').click();
    cy.get('[data-testid="export-docx"]').click();
    cy.get('[data-testid="download-success"]', { timeout: 10000 }).should('be.visible');

    // Export as HTML
    cy.get('button[data-testid="export-dropdown"]').click();
    cy.get('[data-testid="export-html"]').click();
    cy.get('[data-testid="download-success"]', { timeout: 10000 }).should('be.visible');
  });

  it('should include MAV consensus in dossier', () => {
    cy.visit('/dossier');
    cy.get('select[name="project"]').select('IPEX Drug Discovery');
    cy.get('button').contains('Next').click();

    // Enable MAV consensus section
    cy.get('input[name="mav-consensus"]').check();
    cy.get('button').contains('Next').click();
    cy.get('button').contains('Generate').click();
    cy.get('[data-testid="generation-complete"]', { timeout: 90000 }).should('be.visible');

    // Preview and verify MAV section
    cy.get('button').contains('Preview').click();
    cy.get('[data-testid="dossier-preview"]').should('be.visible');
    cy.contains('Multi-Agent Voting Consensus').should('be.visible');
    cy.contains('Agent Contributions').should('be.visible');
  });

  it('should include provenance tracking in dossier', () => {
    cy.visit('/dossier');
    cy.get('select[name="project"]').select('IPEX Drug Discovery');
    cy.get('button').contains('Next').click();

    // Enable provenance section
    cy.get('input[name="provenance"]').check();
    cy.get('button').contains('Next').click();
    cy.get('button').contains('Generate').click();
    cy.get('[data-testid="generation-complete"]', { timeout: 90000 }).should('be.visible');

    // Preview and verify provenance
    cy.get('button').contains('Preview').click();
    cy.get('[data-testid="dossier-preview"]').should('be.visible');
    cy.contains('Provenance Appendix').should('be.visible');
    cy.contains('Data Sources').should('be.visible');
    cy.contains('Retrieval Timestamps').should('be.visible');
  });

  it('should save dossier draft', () => {
    cy.visit('/dossier');
    cy.get('select[name="project"]').select('IPEX Drug Discovery');
    cy.get('button').contains('Next').click();
    cy.get('input[name="executive-summary"]').check();

    // Save as draft
    cy.get('button[data-testid="save-draft"]').click();
    cy.get('input[name="draft-name"]').type('IPEX Dossier Draft');
    cy.get('button').contains('Save').click();
    cy.get('[data-testid="save-success"]').should('be.visible');

    // Navigate to drafts
    cy.visit('/dossier/drafts');
    cy.contains('IPEX Dossier Draft').should('be.visible');
  });

  it('should handle generation errors gracefully', () => {
    cy.visit('/dossier');

    // Try to generate without selecting project
    cy.get('button').contains('Next').click();
    cy.get('[data-testid="error-message"]').should('be.visible');
    cy.contains('Please select a project').should('be.visible');
  });
});
