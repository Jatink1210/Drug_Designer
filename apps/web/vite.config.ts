/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
    plugins: [react(), tailwindcss()],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
    build: {
        chunkSizeWarningLimit: 600,
        // §O-4: Manual chunk splitting to keep initial bundle lean and ensure
        // heavy lab pages load as separate async chunks (LCP + TTI improvement).
        rollupOptions: {
            output: {
                manualChunks(id) {
                    // Vendor: React core — must be in its own chunk for long-term caching
                    if (id.includes("node_modules/react/") || id.includes("node_modules/react-dom/")) {
                        return "vendor-react";
                    }
                    // Vendor: charting / visualisation libs (heavy)
                    if (
                        id.includes("node_modules/recharts") ||
                        id.includes("node_modules/d3") ||
                        id.includes("node_modules/three")
                    ) {
                        return "vendor-charts";
                    }
                    // Vendor: routing + query
                    if (
                        id.includes("node_modules/react-router") ||
                        id.includes("node_modules/@tanstack/react-query")
                    ) {
                        return "vendor-router-query";
                    }
                    // Heavy lab pages — each gets its own async chunk
                    const labPages = [
                        "MoleculeGenerationLabPage",
                        "RetrosynthesisPage",
                        "VaccineLabPage",
                        "PocketLabPage",
                        "MetabolicEngineeringLabPage",
                        "PharmacogenomicsLabPage",
                        "TargetDiscoveryLabPage",
                        "SynthArenaPage",
                        "ScenarioArenaPage",
                        "AdmetPanels",
                    ];
                    for (const page of labPages) {
                        if (id.includes(`/pages/${page}`)) {
                            return `lab-${page.toLowerCase().replace(/page$/, "")}`;
                        }
                    }
                },
            },
        },
    },
    server: {
        port: 5173,
        host: true,
        proxy: {
            "/api": {
                target: "http://127.0.0.1:8000",
                changeOrigin: true,
            },
        },
    },
    test: {
        environment: "jsdom",
        globals: true,
        setupFiles: ["./src/__tests__/setup.ts"],
    },
});
