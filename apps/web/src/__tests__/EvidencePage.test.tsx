/**
 * EvidencePage smoke tests — verifies the evidence page renders key elements.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import EvidencePage from "../pages/EvidencePage";

const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function renderPage() {
    return render(
        <QueryClientProvider client={qc}>
            <BrowserRouter>
                <EvidencePage />
            </BrowserRouter>
        </QueryClientProvider>,
    );
}

describe("EvidencePage", () => {
    it("renders the page header", () => {
        renderPage();
        expect(screen.getByText("Evidence & Literature")).toBeDefined();
    });

    it("renders source filter checkboxes", () => {
        renderPage();
        expect(screen.getByText("PubMed")).toBeDefined();
        expect(screen.getByText("ClinicalTrials")).toBeDefined();
    });
});
