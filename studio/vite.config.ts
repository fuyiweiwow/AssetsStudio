import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const bridgeTarget = process.env.ASSETSSTUDIO_BRIDGE_URL ?? "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 4173,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      "/api/local-generation": {
        target: bridgeTarget,
        changeOrigin: false,
        rewrite: (path) => path.replace(/^\/api\/local-generation/, "/api"),
      },
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 4174,
    strictPort: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
