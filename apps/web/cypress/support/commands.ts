// Custom Cypress commands

/// <reference types="cypress" />

declare global {
  namespace Cypress {
    interface Chainable {
      /**
       * Custom command to login
       * @example cy.login('test@example.com', 'password')
       */
      login(email: string, password: string): Chainable<void>;
      
      /**
       * Custom command to create a project
       * @example cy.createProject('Test Project', 'Description')
       */
      createProject(name: string, description: string): Chainable<string>;
      
      /**
       * Custom command to wait for API call
       * @example cy.waitForApi('@searchDisease')
       */
      waitForApi(alias: string): Chainable<void>;
    }
  }
}

// Login command
Cypress.Commands.add('login', (email: string, password: string) => {
  cy.session([email, password], () => {
    cy.visit('/login');
    cy.get('input[name="email"]').type(email);
    cy.get('input[name="password"]').type(password);
    cy.get('button[type="submit"]').click();
    cy.url().should('include', '/dashboard');
  });
});

// Create project command
Cypress.Commands.add('createProject', (name: string, description: string) => {
  cy.visit('/projects');
  cy.get('button[data-testid="create-project"]').click();
  cy.get('input[name="name"]').type(name);
  cy.get('textarea[name="description"]').type(description);
  cy.get('button[type="submit"]').click();
  
  // Return project ID
  cy.url().then((url) => {
    const projectId = url.split('/').pop();
    return cy.wrap(projectId);
  });
});

// Wait for API call command
Cypress.Commands.add('waitForApi', (alias: string) => {
  cy.wait(alias).its('response.statusCode').should('eq', 200);
});

export {};
