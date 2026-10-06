import { defineConfig, devices } from "@playwright/test";
import { testPython } from "./tests/python-runtime";

export default defineConfig({
  testDir: "./tests",
  testMatch: "app-integration.spec.ts",
  workers: 1,
  timeout: 60_000,
  use: { baseURL: "http://127.0.0.1:5174", trace: "retain-on-failure", actionTimeout: 10_000 },
  webServer: [
    {
      command: `"${testPython}" scripts/run_browser_test_server.py`,
      cwd: "../backend",
      url: "http://127.0.0.1:8001/health",
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5174 --strictPort",
      url: "http://127.0.0.1:5174",
      env: { VITE_API_BASE_URL: "http://127.0.0.1:8001" },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
