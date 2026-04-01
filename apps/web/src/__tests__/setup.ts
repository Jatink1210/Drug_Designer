/**
 * Global test setup — runs before every test file.
 */
import "@testing-library/jest-dom";
import { vi } from "vitest";

// Stub fetch globally to prevent API calls from crashing tests
vi.stubGlobal(
    "fetch",
    vi.fn(() =>
        Promise.resolve({
            ok: true,
            json: () => Promise.resolve({}),
            text: () => Promise.resolve(""),
        }),
    ),
);
