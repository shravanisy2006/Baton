import { defineConfig, devices } from "@playwright/test";

/**
 * Browser tests against the real frontend and the real API, with the API's AI replaced by the scripted stand-in
 * from backend/tests/conftest.py (no Gemini key needed; results are deterministic).
 * Run from frontend/:  npx playwright test   (set PYTHON to your backend venv's python if needed)
 */
const python = process.env.PYTHON ?? "python";

export default defineConfig({
  testDir: "e2e",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { baseURL: "http://localhost:5173", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1360, height: 900 } } }],
  webServer: [
    {
      command: `${python} ../backend/tests/run_with_fake_ai.py`,
      url: "http://127.0.0.1:8000/health",
      env: { BATON_FRESH_DB: "1" },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: "npx vite --port 5173 --strictPort",
      url: "http://localhost:5173",
      env: { VITE_API_URL: "http://localhost:8000" },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
