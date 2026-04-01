/**
 * SearchPage smoke tests — verifies the search page renders key elements.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SearchPage from "../pages/SearchPage";

const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function renderPage() {
    return render(
        <QueryClientProvider client={qc}>
            <BrowserRouter>
                <SearchPage onEntityClick={() => {}} />
            </BrowserRouter>
        </QueryClientProvider>,
    );
}

describe("SearchPage", () => {
    it("renders the page header", () => {
        renderPage();
        expect(screen.getByText("Omniscient Search")).toBeDefined();
    });

    it("renders the search input", () => {
        renderPage();
        expect(screen.getByPlaceholderText(/Search proteins/i)).toBeDefined();
    });

    it("renders the strict evidence toggle", () => {
        renderPage();
        expect(screen.getByText("Assisted")).toBeDefined();
    });
});
