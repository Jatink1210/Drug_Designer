/**
 * G2: SynthArena scenario management E2E tests.
 * Covers: Open SynthArena → Run scenario → Compare outcomes + accessibility.
 */

/// <reference types="cypress" />

// cypress-axe type stubs (package optional at runtime)
declare namespace Cypress {
  interface Chainable {
    injectAxe(): Chainable<void>;
    checkA11y(context?: unknown, options?: unknown): Chainable<void>;
  }
}

describe('SynthArena Scenario Management', () => {
  beforeEach(() => {
    // Stub API responses so tests run without a live backend
    cy.intercept('GET', '/api/scenarios*', {
      statusCode: 200,
      body: {
        scenarios: [
          { id: 'sc-001', name: 'BRCA1 Inhibition', status: 'completed', outcome_score: 0.87 },
          { id: 'sc-002', name: 'TP53 Activation', status: 'running', outcome_score: null },
        ],
        total: 2,
      },
    }).as('getScenarios');

    cy.intercept('POST', '/api/scenarios', {
      statusCode: 201,
      body: { id: 'sc-003', name: 'New Scenario', status: 'queued' },
    }).as('createScenario');

    cy.intercept('GET', '/api/scenarios/sc-001', {
      statusCode: 200,
      body: {
        id: 'sc-001',
        name: 'BRCA1 Inhibition',
        status: 'completed',
        outcome_score: 0.87,
        outcomes: [
          { metric: 'efficacy', value: 0.87, confidence: 0.92 },
          { metric: 'safety', value: 0.78, confidence: 0.85 },
        ],
        comparison: { baseline: 'standard_of_care', delta: +0.12 },
      },
    }).as('getScenarioDetail');

    cy.visit('/syntharena');
  });

  it('loads scenario list on navigation', () => {
    cy.wait('@getScenarios');
    cy.get('[data-testid="scenario-list"]').should('exist');
    cy.get('[data-testid="scenario-item"]').should('have.length.at.least', 1);
  });

  it('creates a new scenario', () => {
    cy.get('[data-testid="new-scenario-btn"]').click();
    cy.get('[data-testid="scenario-name-input"]').type('New Test Scenario');
    cy.get('[data-testid="scenario-submit"]').click();
    cy.wait('@createScenario');
    cy.get('[data-testid="toast-success"]').should('contain.text', 'scenario');
  });

  it('views scenario detail and outcomes', () => {
    cy.wait('@getScenarios');
    cy.get('[data-testid="scenario-item"]').first().click();
    cy.wait('@getScenarioDetail');
    cy.get('[data-testid="outcome-table"]').should('exist');
    cy.get('[data-testid="outcome-row"]').should('have.length.at.least', 2);
  });

  it('compares scenario outcomes', () => {
    cy.wait('@getScenarios');
    cy.get('[data-testid="scenario-item"]').first().click();
    cy.wait('@getScenarioDetail');
    cy.get('[data-testid="comparison-chart"]').should('exist');
    cy.get('[data-testid="baseline-label"]').should('contain.text', 'standard_of_care');
  });

  it('has no critical accessibility violations', () => {
    cy.wait('@getScenarios');
    cy.injectAxe();
    cy.checkA11y(undefined, {
      rules: { 'color-contrast': { enabled: false } },
    });
  });
});
