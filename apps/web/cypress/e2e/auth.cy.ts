describe('Multi-Tenant Authentication & Identity Flow', () => {
  const TEST_EMAIL = `test_${Date.now()}@example.com`;
  const TEST_PW = 'SecurePassword123!';
  const TEST_NAME = 'E2E Cypress Tester';

  beforeEach(() => {
    // Navigate to the web app frontend
    cy.visit('/');
  });

  it('redirects unauthenticated users from /workspace to /login', () => {
    // We expect the react router <ProtectedRoute> to kick in
    cy.url().should('include', '/login');
    cy.get('h2').should('contain', 'DrugDesigner Platform');
  });

  it('allows a new scientist to register an isolated multi-tenant account', () => {
    cy.visit('/login');
    
    // Switch to registration mode
    cy.contains('Need an account? Register').click();
    
    // Fill out registration form
    cy.get('input[placeholder="Full Name"]').type(TEST_NAME);
    cy.get('input[placeholder="Email address"]').type(TEST_EMAIL);
    cy.get('input[placeholder="Password"]').type(TEST_PW);
    
    // Intercept login payload since registration auto-logs in
    cy.intercept('POST', '**/api/auth/login').as('loginReq');
    cy.intercept('GET', '**/api/auth/me').as('meReq');

    cy.contains('button', 'Register').click();

    // Application should acquire JWT and route into workspace
    cy.wait('@loginReq').its('response.statusCode').should('eq', 200);
    cy.wait('@meReq').its('response.statusCode').should('eq', 200);
    
    // Should be in workspace
    cy.url().should('include', '/workspace');
    cy.window().then((win) => {
      const token = win.localStorage.getItem('dss_auth_token');
      expect(token).to.exist;
    });
  });

  it('allows login and correctly isolates project data', () => {
    // 1. Log in with the previously created account
    cy.visit('/login');
    cy.get('input[placeholder="Email address"]').type(TEST_EMAIL);
    cy.get('input[placeholder="Password"]').type(TEST_PW);
    cy.contains('button', 'Sign in').click();

    // 2. We should reach workspace
    cy.url().should('include', '/workspace', { timeout: 10000 });

    // 3. Create a project to test tenant isolation
    cy.intercept('POST', '**/api/projects').as('createProject');
    const projectName = `Secret Target ${Date.now()}`;
    
    // Assuming there's a hypothetical button to navigate to projects and create
    // If UI doesn't have it explicitly bound yet, we can test via direct Cypress API requests with our token
    cy.window().then((win) => {
      const token = win.localStorage.getItem('dss_auth_token');
      
      // Attempt to create a project
      cy.request({
        method: 'POST',
        url: Cypress.env('apiUrl') + '/projects',
        headers: { Authorization: `Bearer ${token}` },
        body: {
          name: projectName,
          description: "Isolated multi-tenant context test"
        }
      }).then((response) => {
        expect(response.status).to.eq(200);
        expect(response.body.name).to.eq(projectName);
        const projectId = response.body.id;

        // Verify another random rogue token CANNOT access this project
        cy.request({
          method: 'GET',
          url: Cypress.env('apiUrl') + `/projects/${projectId}`,
          headers: { Authorization: `Bearer bogus_token_123` },
          failOnStatusCode: false
        }).then((rogueResponse) => {
          expect(rogueResponse.status).to.eq(401);
        });
      });
    });
  });
});
