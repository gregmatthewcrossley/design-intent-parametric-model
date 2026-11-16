import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

// `npm run build` writes the bundle where `dipm serve` serves it from (gitignored).
// `npm run dev` proxies /api (HTTP + WebSocket) to a running `python -m dipm serve <design> --no-open`.
const api = process.env.DIPM_API ?? "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [preact()],
  build: {
    outDir: "../src/dipm/server/static",
    emptyOutDir: true,
    chunkSizeWarningLimit: 900,
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      "/api": { target: api, changeOrigin: false, ws: true },
    },
  },
  test: {
    include: ["tests/**/*.test.ts"],
    environment: "node",
  },
} as any);
