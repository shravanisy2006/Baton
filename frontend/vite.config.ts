/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The deployed commit (Vercel sets VERCEL_GIT_COMMIT_SHA at build time), shown in the home page footer next to the
// server's commit from /health, so anyone can check which version is live.
const webVersion = (process.env.VERCEL_GIT_COMMIT_SHA ?? "dev").slice(0, 7);

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: { __WEB_VERSION__: JSON.stringify(webVersion) },
  server: { port: 5173 },
  test: {
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    globals: true,
  },
});
