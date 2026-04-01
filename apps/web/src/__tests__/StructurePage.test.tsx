/**
 * StructurePage smoke tests — verifies the structure page renders key elements.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import StructurePage from "../pages/StructurePage";

const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function renderPage() {
    return render(
        <QueryClientProvider client={qc}>
            <BrowserRouter>
                <StructurePage />
            </BrowserRouter>
        </QueryClientProvider>,
    );
}

describe("StructurePage", () => {
    it("renders the structure navigator", () => {
        renderPage();
        expect(screen.getByText("Structure Navigator")).toBeDefined();
    });

    it("renders PDB input field", () => {
        renderPage();
        expect(screen.getByPlaceholderText(/PDB ID/i)).toBeDefined();
    });
});
