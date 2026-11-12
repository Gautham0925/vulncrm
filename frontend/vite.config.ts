/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = process.env.VITE_API_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(["/api", "/graphql", "/oauth", "/oidc", "/saml", "/.well-known"].map((p) => [p, { target: api, changeOrigin: false }])),
  },
  test: { environment: "jsdom", setupFiles: ["./src/test-setup.ts"], globals: true },
});
