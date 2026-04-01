/**
 * SettingsPage smoke tests — verifies the settings page renders key sections.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SettingsPage from "../pages/SettingsPage";

// Mock API functions to return sensible defaults
vi.mock("@/lib/api", async () => {
    const actual = await vi.importActual<Record<string, unknown>>("@/lib/api");
    return {
        ...actual,
        settingsGetAPI: vi.fn(() =>
            Promise.resolve({ compute_mode: "auto", runtime: "llama.cpp", model_id: "BioMistral-7B", privacy_mode: false, setup_complete: true }),
        ),
        runtimesListAPI: vi.fn(() =>
            Promise.resolve({ capabilities: { cpu_cores: 8, ram_gb: 16, gpu: "none", gpu_name: null, vram_gb: 0, airllm_installed: false }, available: [], active: "llama.cpp" }),
        ),
        modelsCatalogAPI: vi.fn(() => Promise.resolve([])),
        modelsInstalledAPI: vi.fn(() => Promise.resolve([])),
        ensureApiBase: vi.fn(() => Promise.resolve("")),
    };
});

const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function renderPage() {
    return render(
        <QueryClientProvider client={qc}>
            <BrowserRouter>
                <SettingsPage />
            </BrowserRouter>
        </QueryClientProvider>,
    );
}

describe("SettingsPage", () => {
    it("renders the page header", async () => {
        renderPage();
        expect(await screen.findByText("Settings")).toBeDefined();
    });

    it("renders compute mode section", async () => {
        renderPage();
        expect(await screen.findByText("Compute & Runtime")).toBeDefined();
    });

    it("renders compute mode buttons", async () => {
        renderPage();
        expect(await screen.findByText("Auto")).toBeDefined();
    });
});
