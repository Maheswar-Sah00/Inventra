/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  return {
    plugins: [react()],
    server: {
      port: 5173,
      // In development the browser calls /api on the Vite server, which forwards to FastAPI.
      proxy: {
        "/api": { target: env.VITE_DEV_API_PROXY_TARGET || "http://localhost:8000", changeOrigin: true },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/setupTests.ts"],
    },
  };
});
