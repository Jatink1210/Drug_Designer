/**
 * Test Utilities
 * 
 * Task 18.2: Write frontend unit tests
 * 
 * Provides common test utilities and custom render functions
 */

import { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

/**
 * Custom render function that wraps components with common providers
 */
export function renderWithRouter(
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  return render(ui, {
    wrapper: ({ children }) => <BrowserRouter>{children}</BrowserRouter>,
    ...options,
  });
}

/**
 * Mock fetch response helper
 */
export function mockFetchResponse(data: any, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    json: async () => data,
    text: async () => JSON.stringify(data),
    headers: new Headers(),
    redirected: false,
    statusText: ok ? 'OK' : 'Error',
    type: 'basic' as ResponseType,
    url: '',
    clone: function() { return this; },
    body: null,
    bodyUsed: false,
    arrayBuffer: async () => new ArrayBuffer(0),
    blob: async () => new Blob(),
    formData: async () => new FormData(),
  } as Response);
}

/**
 * Wait for async updates
 */
export const waitForAsync = () => new Promise(resolve => setTimeout(resolve, 0));

/**
 * Create mock API response with envelope
 */
export function createMockApiResponse<T>(data: T, requestId = 'test-123') {
  return {
    data,
    request_id: requestId,
    timestamp: new Date().toISOString(),
  };
}

/**
 * Mock window.matchMedia
 */
export function mockMatchMedia(matches = false) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => true,
    }),
  });
}

/**
 * Mock IntersectionObserver
 */
export function mockIntersectionObserver() {
  global.IntersectionObserver = class IntersectionObserver {
    constructor() {}
    disconnect() {}
    observe() {}
    takeRecords() { return []; }
    unobserve() {}
  } as any;
}

/**
 * Create mock navigation items
 */
export function createMockNavigationItems(count = 3) {
  return Array.from({ length: count }, (_, i) => ({
    label: `Item ${i + 1}`,
    href: `/item-${i + 1}`,
    active: i === 0,
  }));
}

/**
 * Create mock search response
 */
export function createMockSearchResponse(query = 'test') {
  return {
    query,
    intent: { intent: 'search', search_term: query, method: 'semantic' },
    summary_stats: {
      total_results: 10,
      categories_found: 2,
      pubmed_count: 5,
      clinical_trials_count: 3,
      sources_queried: 4,
    },
    categories: {
      proteins: {
        columns: ['id', 'name', 'organism'],
        rows: [
          { id: 'P12345', name: 'Test Protein', organism: 'Human' },
        ],
        total: 1,
      },
    },
    preview_graph: {
      nodes: [
        { id: '1', label: 'Node 1', type: 'protein' },
        { id: '2', label: 'Node 2', type: 'gene' },
      ],
      edges: [
        { source: '1', target: '2', label: 'interacts', weight: 0.8 },
      ],
    },
    provenance: {
      sources_hit: ['uniprot', 'pubmed'],
      timestamps: { uniprot: 1234567890, pubmed: 1234567891 },
    },
    timings: { total: 1.5, search: 0.8, graph: 0.7 },
    errors: [],
  };
}

/**
 * Create mock health response
 */
export function createMockHealthResponse(status = 'healthy') {
  return {
    status,
    service: 'drug-designer',
    version: '1.0.0',
    check_ms: 10,
    ollama_ok: true,
    connectors_active: 5,
    connectors_total: 10,
    connectors_degraded: 0,
    runtime_mode: 'local',
    active_model: 'llama3',
  };
}

/**
 * Create mock structure summary
 */
export function createMockStructureSummary(pdbId = '1ABC') {
  return {
    pdb_id: pdbId,
    title: 'Test Structure',
    classification: 'HYDROLASE',
    organism: 'Homo sapiens',
    expression_system: 'Escherichia coli',
    method: 'X-RAY DIFFRACTION',
    resolution: 2.5,
    r_work: 0.18,
    r_free: 0.22,
    space_group: 'P 21 21 21',
    cell_dimensions: { a: 50.0, b: 60.0, c: 70.0 },
    deposition_date: '2020-01-01',
    release_date: '2020-06-01',
    revision_date: '2021-01-01',
    primary_citation: {
      title: 'Test Paper',
      journal: 'Nature',
      year: 2020,
      doi: '10.1038/test',
      pmid: '12345678',
    },
    macromolecules: [],
    ligands: [],
    assemblies: [],
    revision_count: 1,
    revision_history: [],
    downloads: {},
    url: `https://www.rcsb.org/structure/${pdbId}`,
  };
}

export * from '@testing-library/react';
