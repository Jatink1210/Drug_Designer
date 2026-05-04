/**
 * G2: Runtime configuration E2E tests.
 * Covers: Configure runtime → Set Ollama model → Run inference test.
 * Also covers: Local agent health check → View logs → WebSocket stream.
 */

/// <reference types="cypress" />

// cypress-axe type stubs (package optional at runtime)
declare namespace Cypress {
  interface Chainable {
    injectAxe(): Chainable<void>;
    checkA11y(context?: unknown, options?: unknown): Chainable<void>;
  }
}

describe('Runtime Configuration', () => {
  beforeEach(() => {
    cy.intercept('GET', '/api/runtime/config', {
      statusCode: 200,
      body: {
        llm_provider: 'ollama',
        model: 'llama3.1:8b',
        ollama_base_url: 'http://localhost:11434',
        temperature: 0.7,
        max_tokens: 4096,
      },
    }).as('getRuntimeConfig');

    cy.intercept('PUT', '/api/runtime/config', {
      statusCode: 200,
      body: { status: 'updated', model: 'mistral:7b' },
    }).as('updateRuntimeConfig');

    cy.intercept('GET', '/api/runtime/models', {
      statusCode: 200,
      body: {
        models: [
          { name: 'llama3.1:8b', size_gb: 4.7, status: 'available' },
          { name: 'mistral:7b', size_gb: 4.1, status: 'available' },
          { name: 'codellama:13b', size_gb: 7.4, status: 'available' },
        ],
      },
    }).as('getModels');

    cy.intercept('POST', '/api/runtime/test-inference', {
      statusCode: 200,
      body: { success: true, latency_ms: 342, tokens_per_second: 28.5 },
    }).as('testInference');

    cy.visit('/settings/runtime');
  });

  it('loads current runtime configuration', () => {
    cy.wait('@getRuntimeConfig');
    cy.get('[data-testid="runtime-provider"]').should('contain.text', 'ollama');
    cy.get('[data-testid="runtime-model"]').should('contain.text', 'llama3.1:8b');
  });

  it('lists available Ollama models', () => {
    cy.wait('@getModels');
    cy.get('[data-testid="model-list"]').should('exist');
    cy.get('[data-testid="model-option"]').should('have.length', 3);
  });

  it('selects a different model and saves', () => {
    cy.wait('@getRuntimeConfig');
    cy.get('[data-testid="model-select"]').select('mistral:7b');
    cy.get('[data-testid="save-runtime-btn"]').click();
    cy.wait('@updateRuntimeConfig');
    cy.get('[data-testid="toast-success"]').should('exist');
  });

  it('runs inference test after configuration', () => {
    cy.wait('@getRuntimeConfig');
    cy.get('[data-testid="test-inference-btn"]').click();
    cy.wait('@testInference');
    cy.get('[data-testid="inference-result"]').should('contain.text', 'latency');
  });

  it('has no critical accessibility violations on runtime page', () => {
    cy.wait('@getRuntimeConfig');
    cy.injectAxe();
    cy.checkA11y();
  });
});

describe('Local Agent Health Check', () => {
  beforeEach(() => {
    cy.intercept('GET', '/api/local-agent/health', {
      statusCode: 200,
      body: {
        status: 'healthy',
        uptime_seconds: 3600,
        model_loaded: 'llama3.1:8b',
        inference_count: 47,
        last_inference_ms: 312,
      },
    }).as('getAgentHealth');

    cy.intercept('GET', '/api/local-agent/logs*', {
      statusCode: 200,
      body: {
        logs: [
          { timestamp: '2025-01-01T10:00:00Z', level: 'INFO', message: 'Agent started' },
          { timestamp: '2025-01-01T10:00:05Z', level: 'INFO', message: 'Model loaded: llama3.1:8b' },
          { timestamp: '2025-01-01T10:00:10Z', level: 'DEBUG', message: 'Inference completed in 312ms' },
        ],
        total: 3,
      },
    }).as('getAgentLogs');

    cy.visit('/settings/local-agent');
  });

  it('shows agent health status', () => {
    cy.wait('@getAgentHealth');
    cy.get('[data-testid="agent-status"]').should('contain.text', 'healthy');
    cy.get('[data-testid="agent-model"]').should('contain.text', 'llama3.1:8b');
  });

  it('displays agent logs', () => {
    cy.wait('@getAgentLogs');
    cy.get('[data-testid="log-viewer"]').should('exist');
    cy.get('[data-testid="log-entry"]').should('have.length', 3);
  });

  it('shows WebSocket connection status indicator', () => {
    cy.get('[data-testid="ws-status-indicator"]').should('exist');
    // Status should be one of: connected, disconnected, connecting
    cy.get('[data-testid="ws-status-indicator"]').invoke('attr', 'data-status').should('match', /connected|disconnected|connecting/);
  });

  it('refreshes logs on demand', () => {
    cy.get('[data-testid="refresh-logs-btn"]').click();
    cy.wait('@getAgentLogs');
    cy.get('[data-testid="log-entry"]').should('have.length.at.least', 1);
  });

  it('has no critical accessibility violations on agent page', () => {
    cy.wait('@getAgentHealth');
    cy.injectAxe();
    cy.checkA11y();
  });
});
