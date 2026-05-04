/**
 * API Module Tests
 * 
 * Task 18.2: Write frontend unit tests
 * Tests for API integration and mocking
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  ensureApiBase,
  searchAPI,
  healthAPI,
  structureSummaryAPI,
  dockingRunAPI,
  moleculeScoreAPI,
} from './api';

describe('API Module', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('ensureApiBase', () => {
    it('returns default API base in browser mode', async () => {
      const base = await ensureApiBase();
      expect(base).toBe('/api/v1');
    });

    it('caches the API base resolution', async () => {
      const base1 = await ensureApiBase();
      const base2 = await ensureApiBase();
      expect(base1).toBe(base2);
    });
  });

  describe('searchAPI', () => {
    it('makes POST request with search query', async () => {
      const mockResponse = {
        data: {
          query: 'test',
          summary_stats: { total_results: 10 },
          categories: {},
          preview_graph: { nodes: [], edges: [] },
          provenance: { sources_hit: [], timestamps: {} },
          timings: {},
          errors: [],
        },
        request_id: '123',
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await searchAPI({ query: 'test' });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/v1/search',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: 'test' }),
        })
      );

      expect(result).toEqual(mockResponse.data);
    });

    it('handles search with filters', async () => {
      const mockResponse = {
        data: { query: 'test', summary_stats: {}, categories: {} },
        request_id: '123',
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      await searchAPI({
        query: 'test',
        filters: { type: 'protein' },
        limit: 50,
      });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/v1/search',
        expect.objectContaining({
          body: JSON.stringify({
            query: 'test',
            filters: { type: 'protein' },
            limit: 50,
          }),
        })
      );
    });

    it('throws error on failed request', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await expect(searchAPI({ query: 'test' })).rejects.toThrow();
    });
  });

  describe('healthAPI', () => {
    it('makes GET request to health endpoint', async () => {
      const mockResponse = {
        data: {
          status: 'healthy',
          service: 'drug-designer',
          version: '1.0.0',
        },
        request_id: '123',
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await healthAPI();

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/v1/health',
        expect.objectContaining({
          credentials: 'include',
          cache: 'no-store',
        })
      );

      expect(result).toEqual(mockResponse.data);
    });

    it('handles health check failure', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 503,
      });

      await expect(healthAPI()).rejects.toThrow();
    });
  });

  describe('structureSummaryAPI', () => {
    it('fetches structure summary by PDB ID', async () => {
      const mockResponse = {
        data: {
          pdb_id: '1ABC',
          title: 'Test Structure',
          method: 'X-RAY DIFFRACTION',
          resolution: 2.5,
        },
        request_id: '123',
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await structureSummaryAPI('1ABC');

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/v1/structure/1ABC',
        expect.any(Object)
      );

      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('dockingRunAPI', () => {
    it('submits docking job', async () => {
      const mockResponse = {
        data: {
          run_id: 'dock-123',
          status: 'queued',
          engine: 'vina',
        },
        request_id: '123',
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const request = {
        receptor_path: '/path/to/receptor.pdb',
        ligand_path: '/path/to/ligand.sdf',
        center: [0, 0, 0],
      };

      const result = await dockingRunAPI(request);

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/v1/docking/run',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(request),
        })
      );

      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('moleculeScoreAPI', () => {
    it('scores multiple SMILES strings', async () => {
      const mockResponse = {
        data: [
          {
            smiles: 'CCO',
            mw: 46.07,
            logp: -0.18,
            hbd: 1,
            hba: 1,
            tpsa: 20.23,
            rotatable_bonds: 0,
            lipinski_violations: 0,
            druglikeness: 'good',
          },
        ],
        request_id: '123',
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await moleculeScoreAPI(['CCO']);

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/v1/molecules/score',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ smiles: ['CCO'] }),
        })
      );

      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Error Handling', () => {
    it('handles network errors', async () => {
      (global.fetch as any).mockRejectedValueOnce(new Error('Network error'));

      await expect(healthAPI()).rejects.toThrow('Network error');
    });

    it('handles malformed JSON responses', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new Error('Invalid JSON');
        },
      });

      await expect(healthAPI()).rejects.toThrow();
    });

    it('unwraps ResponseEnvelope correctly', async () => {
      const mockResponse = {
        data: { status: 'ok' },
        request_id: '123',
        timestamp: '2024-01-01T00:00:00Z',
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await healthAPI();
      expect(result).toEqual({ status: 'ok' });
    });

    it('handles responses without envelope', async () => {
      const mockResponse = { status: 'ok' };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await healthAPI();
      expect(result).toEqual({ status: 'ok' });
    });
  });

  describe('Credentials and Headers', () => {
    it('includes credentials in requests', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: {}, request_id: '123' }),
      });

      await healthAPI();

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          credentials: 'include',
        })
      );
    });

    it('sets Content-Type header for POST requests', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: {}, request_id: '123' }),
      });

      await searchAPI({ query: 'test' });

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });
  });
});
