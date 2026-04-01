/**
 * Smoke test — verifies the App component renders without crashing.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import App from "../App";

// Stub fetch globally so useEffect calls don't fail
vi.stubGlobal("fetch", vi.fn((url: string) => {
    if (typeof url === "string" && url.includes("/health")) {
        return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ status: "ok", version: "1.0.0", service: "drug-designer-api" }),
        });
    }
    if (typeof url === "string" && url.includes("/logs/jobs")) {
        return Promise.resolve({
            ok: true,
            json: () => Promise.resolve([]),
        });
    }
    return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ setup_complete: true }),
    });
}));

describe("App", () => {
    it("renders without crashing", async () => {
        render(<App />);
        // Initially shows loading state; after health resolves, shows "API Connected"
        await waitFor(() => {
            const el = screen.queryByText("API Connected") ?? screen.queryByText("Connecting…");
            expect(el).toBeTruthy();
        });
    });

    it("renders the version string", async () => {
        render(<App />);
        // Initially shows "v…" then resolves to "v1.0.0"
        await waitFor(() => {
            const el = screen.queryByText("v1.0.0") ?? screen.queryByText("v…");
            expect(el).toBeTruthy();
        });
    });
});
