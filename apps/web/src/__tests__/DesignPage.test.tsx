/**
 * DesignPage smoke tests — verifies the molecule design page renders key elements.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DesignPage from "../pages/DesignPage";

const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function renderPage() {
    return render(
        <QueryClientProvider client={qc}>
            <BrowserRouter>
                <DesignPage />
            </BrowserRouter>
        </QueryClientProvider>,
    );
}

describe("DesignPage", () => {
    it("renders the page header", () => {
        renderPage();
        expect(screen.getByText("Molecule Design Studio")).toBeDefined();
    });

    it("renders the step labels", () => {
        renderPage();
        expect(screen.getByText("Target & Site")).toBeDefined();
    });
});
