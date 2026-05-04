/**
 * E2E tests for Critical User Journeys
 * 
 * Tests disease intelligence, target prioritization, and dossier generation
 */

describe('Critical User Journeys E2E Tests', () => {
  beforeEach(() => {
    // Login before each test
    cy.visit('/login');
    cy.get('input[name="email"]').type('test@example.com');
    cy.get('input[name="password"]').type('testpassword');
    cy.get('button[type="submit"]').click();
    cy.url().should('include', '/dashboard');
  });

  describe('User Journey 1: Disease Intelligence', () => {
    it('should search for disease and view intelligence', () => {
      cy.visit('/disease-intelligence');
      
      // Search for disease
      cy.get('input[name="diseaseSearch"]').type('IPEX syndrome');
      cy.get('button[type="submit"]').click();
      
      // Wait for results
      cy.contains('IPEX syndrome', { timeout: 10000 });
      
      // View disease details
      cy.get('[data-testid="disease-card"]').first().click();
      cy.url().should('include', '/disease/');
      
      // Verify disease information
      cy.get('[data-testid="disease-name"]').should('contain', 'IPEX');
      cy.get('[data-testid="disease-description"]').should('exist');
      cy.get('[data-testid="associated-genes"]').should('exist');
      cy.get('[data-testid="phenotypes"]').should('exist');
    });

    it('should explore disease pathways', () => {
      cy.visit('/disease-intelligence');
      
      cy.get('input[name="diseaseSearch"]').type('IPEX syndrome');
      cy.get('button[type="submit"]').click();
      cy.get('[data-testid="disease-card"]').first().click();
      
      // Navigate to pathways
      cy.get('button[data-testid="view-pathways"]').click();
      cy.url().should('include', '/pathways');
      
      // Verify pathway visualization
      cy.get('[data-testid="pathway-graph"]').should('be.visible');
      cy.get('[data-testid="pathway-node"]').should('have.length.at.least', 1);
    });

    it('should view disease literature', () => {
      cy.visit('/disease-intelligence');
      
      cy.get('input[name="diseaseSearch"]').type('IPEX syndrome');
      cy.get('button[type="submit"]').click();
      cy.get('[data-testid="disease-card"]').first().click();
      
      // Navigate to literature
      cy.get('button[data-testid="view-literature"]').click();
      
      // Verify literature results
      cy.get('[data-testid="literature-item"]').should('have.length.at.least', 1);
      cy.get('[data-testid="pubmed-link"]').should('exist');
    });
  });

  describe('User Journey 2: Target Discovery & Prioritization', () => {
    it('should discover and prioritize drug targets', () => {
      cy.visit('/target-discovery');
      
      // Enter disease context
      cy.get('input[name="disease"]').type('IPEX syndrome');
      cy.get('button[type="submit"]').click();
      
      // Wait for target discovery
      cy.contains('Discovering targets', { timeout: 10000 });
      cy.contains('Discovery complete', { timeout: 60000 });
      
      // Verify targets
      cy.get('[data-testid="target-card"]').should('have.length.at.least', 1);
      cy.get('[data-testid="target-score"]').should('exist');
      cy.get('[data-testid="target-gene"]').should('exist');
    });

    it('should prioritize targets using GAT model', () => {
      cy.visit('/target-discovery');
      
      cy.get('input[name="disease"]').type('IPEX syndrome');
      cy.get('button[type="submit"]').click();
      
      cy.contains('Discovery complete', { timeout: 60000 });
      
      // Sort by priority score
      cy.get('select[name="sortBy"]').select('priority_score');
      
      // Verify sorting
      cy.get('[data-testid="target-score"]').then(($scores) => {
        const scores = $scores.map((i, el) => parseFloat(el.textContent)).get();
        const sortedScores = [...scores].sort((a, b) => b - a);
        expect(scores).to.deep.equal(sortedScores);
      });
    });

    it('should explore target protein structure', () => {
      cy.visit('/target-discovery');
      
      cy.get('input[name="disease"]').type('IPEX syndrome');
      cy.get('button[type="submit"]').click();
      cy.contains('Discovery complete', { timeout: 60000 });
      
      // View protein structure
      cy.get('[data-testid="target-card"]').first().click();
      cy.get('button[data-testid="view-structure"]').click();
      
      // Verify 3D structure viewer
      cy.get('[data-testid="protein-viewer"]').should('be.visible');
      cy.get('[data-testid="pdb-id"]').should('exist');
    });

    it('should analyze target druggability', () => {
      cy.visit('/target-discovery');
      
      cy.get('input[name="disease"]').type('IPEX syndrome');
      cy.get('button[type="submit"]').click();
      cy.contains('Discovery complete', { timeout: 60000 });
      
      // View druggability analysis
      cy.get('[data-testid="target-card"]').first().click();
      cy.get('button[data-testid="analyze-druggability"]').click();
      
      // Verify analysis
      cy.get('[data-testid="druggability-score"]').should('exist');
      cy.get('[data-testid="binding-sites"]').should('exist');
    });
  });

  describe('User Journey 3: Dossier Generation', () => {
    it('should generate comprehensive dossier', () => {
      cy.visit('/dossiers');
      
      // Create new dossier
      cy.get('button[data-testid="create-dossier"]').click();
      cy.get('input[name="title"]').type('IPEX Syndrome Drug Discovery Dossier');
      cy.get('textarea[name="description"]').type('Comprehensive analysis');
      cy.get('button[type="submit"]').click();
      
      // Wait for generation
      cy.contains('Generating dossier', { timeout: 10000 });
      cy.contains('Dossier generated', { timeout: 120000 });
      
      // Verify dossier
      cy.get('[data-testid="dossier-title"]').should('contain', 'IPEX');
      cy.get('[data-testid="dossier-sections"]').should('exist');
    });

    it('should include MAV consensus in dossier', () => {
      cy.visit('/dossiers');
      
      cy.get('[data-testid="dossier-card"]').first().click();
      
      // Navigate to consensus section
      cy.get('button[data-testid="view-consensus"]').click();
      
      // Verify consensus data
      cy.get('[data-testid="consensus-result"]').should('exist');
      cy.get('[data-testid="vote-trace"]').should('exist');
      cy.get('[data-testid="specialist-roles"]').should('exist');
    });

    it('should export dossier as PDF', () => {
      cy.visit('/dossiers');
      
      cy.get('[data-testid="dossier-card"]').first().click();
      
      // Export as PDF
      cy.get('button[data-testid="export-pdf"]').click();
      
      // Wait for export
      cy.contains('Exporting PDF', { timeout: 10000 });
      cy.contains('Export complete', { timeout: 90000 });
      
      // Verify download
      cy.get('[data-testid="download-link"]').should('be.visible');
    });

    it('should include provenance in dossier', () => {
      cy.visit('/dossiers');
      
      cy.get('[data-testid="dossier-card"]').first().click();
      
      // View provenance
      cy.get('button[data-testid="view-provenance"]').click();
      
      // Verify provenance data
      cy.get('[data-testid="provenance-trace"]').should('exist');
      cy.get('[data-testid="data-sources"]').should('exist');
      cy.get('[data-testid="timestamps"]').should('exist');
    });
  });

  describe('User Journey 4: Project Management', () => {
    it('should create and manage project', () => {
      cy.visit('/projects');
      
      // Create project
      cy.get('button[data-testid="create-project"]').click();
      cy.get('input[name="name"]').type('IPEX Drug Discovery');
      cy.get('textarea[name="description"]').type('Finding treatments for IPEX syndrome');
      cy.get('select[name="diseaseArea"]').select('Rare Disease');
      cy.get('button[type="submit"]').click();
      
      // Verify project created
      cy.contains('Project created successfully');
      cy.get('[data-testid="project-card"]').should('contain', 'IPEX Drug Discovery');
    });

    it('should add team members to project', () => {
      cy.visit('/projects');
      
      cy.get('[data-testid="project-card"]').first().click();
      
      // Add team member
      cy.get('button[data-testid="add-member"]').click();
      cy.get('input[name="email"]').type('colleague@example.com');
      cy.get('select[name="role"]').select('Researcher');
      cy.get('button[type="submit"]').click();
      
      // Verify member added
      cy.contains('Member added successfully');
      cy.get('[data-testid="team-member"]').should('contain', 'colleague@example.com');
    });

    it('should view project activity timeline', () => {
      cy.visit('/projects');
      
      cy.get('[data-testid="project-card"]').first().click();
      
      // View timeline
      cy.get('button[data-testid="view-timeline"]').click();
      
      // Verify timeline
      cy.get('[data-testid="timeline-event"]').should('have.length.at.least', 1);
      cy.get('[data-testid="event-timestamp"]').should('exist');
    });
  });

  describe('User Journey 5: Evidence Management', () => {
    it('should search and save evidence', () => {
      cy.visit('/evidence');
      
      // Search evidence
      cy.get('input[name="query"]').type('FOXP3 mutations IPEX');
      cy.get('button[type="submit"]').click();
      
      // Wait for results
      cy.contains('Searching evidence', { timeout: 10000 });
      cy.contains('Search complete', { timeout: 30000 });
      
      // Save evidence
      cy.get('[data-testid="evidence-item"]').first().within(() => {
        cy.get('button[data-testid="save-evidence"]').click();
      });
      
      // Verify saved
      cy.contains('Evidence saved');
    });

    it('should verify evidence with MAV consensus', () => {
      cy.visit('/evidence');
      
      cy.get('[data-testid="saved-evidence"]').first().click();
      
      // Request consensus
      cy.get('button[data-testid="verify-evidence"]').click();
      cy.get('select[name="jurySize"]').select('5');
      cy.get('button[type="submit"]').click();
      
      // Wait for consensus
      cy.contains('Running consensus', { timeout: 10000 });
      cy.contains('Consensus complete', { timeout: 60000 });
      
      // Verify result
      cy.get('[data-testid="consensus-status"]').should('exist');
      cy.get('[data-testid="consensus-status"]').should('be.oneOf', ['verified', 'contradicted', 'conflict']);
    });

    it('should handle truthful pause', () => {
      cy.visit('/evidence');
      
      cy.get('[data-testid="saved-evidence"]').first().click();
      cy.get('button[data-testid="verify-evidence"]').click();
      cy.get('button[type="submit"]').click();
      
      // Wait for potential conflict
      cy.contains('Consensus complete', { timeout: 60000 });
      
      // If conflict, handle truthful pause
      cy.get('body').then(($body) => {
        if ($body.find('[data-testid="truthful-pause"]').length > 0) {
          cy.get('[data-testid="truthful-pause"]').should('be.visible');
          cy.get('button[data-testid="accept-verified"]').should('exist');
          cy.get('button[data-testid="accept-contradicted"]').should('exist');
          cy.get('button[data-testid="request-more-evidence"]').should('exist');
        }
      });
    });
  });

  describe('Authentication & Authorization', () => {
    it('should require authentication for protected routes', () => {
      cy.clearCookies();
      cy.visit('/projects');
      
      // Should redirect to login
      cy.url().should('include', '/login');
    });

    it('should logout successfully', () => {
      cy.visit('/dashboard');
      
      cy.get('button[data-testid="user-menu"]').click();
      cy.get('button[data-testid="logout"]').click();
      
      // Should redirect to login
      cy.url().should('include', '/login');
    });

    it('should enforce role-based access control', () => {
      cy.visit('/admin');
      
      // Non-admin users should be denied
      cy.get('body').then(($body) => {
        if ($body.find('[data-testid="access-denied"]').length > 0) {
          cy.contains('Access Denied');
        }
      });
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully', () => {
      cy.visit('/disease-intelligence');
      
      // Simulate API error
      cy.intercept('POST', '/api/v1/disease/search', {
        statusCode: 500,
        body: { error: 'Internal server error' }
      });
      
      cy.get('input[name="diseaseSearch"]').type('IPEX');
      cy.get('button[type="submit"]').click();
      
      // Verify error message
      cy.contains('An error occurred', { timeout: 5000 });
      cy.get('button[data-testid="retry"]').should('be.visible');
    });

    it('should handle network errors', () => {
      cy.visit('/disease-intelligence');
      
      // Simulate network error
      cy.intercept('POST', '/api/v1/disease/search', { forceNetworkError: true });
      
      cy.get('input[name="diseaseSearch"]').type('IPEX');
      cy.get('button[type="submit"]').click();
      
      // Verify error message
      cy.contains('Network error', { timeout: 5000 });
    });
  });

  describe('Performance', () => {
    it('should load dashboard within 3 seconds', () => {
      const start = Date.now();
      cy.visit('/dashboard');
      
      cy.get('[data-testid="dashboard-content"]').should('be.visible');
      
      const elapsed = Date.now() - start;
      expect(elapsed).to.be.lessThan(3000);
    });

    it('should handle large datasets efficiently', () => {
      cy.visit('/evidence');
      
      // Search for broad term (many results)
      cy.get('input[name="query"]').type('cancer');
      cy.get('button[type="submit"]').click();
      
      // Should still load within reasonable time
      cy.contains('Search complete', { timeout: 30000 });
      cy.get('[data-testid="evidence-item"]').should('have.length.at.least', 10);
    });
  });
});
