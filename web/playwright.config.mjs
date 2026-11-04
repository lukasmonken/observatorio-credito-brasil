import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  testMatch: "*.spec.mjs",
  workers: 2,
  timeout: 30000,
  use: {
    baseURL: "http://127.0.0.1:4173/dist/",
    headless: true,
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
  webServer: {
    command: "python3 -m http.server 4173 --bind 127.0.0.1 --directory .",
    url: "http://127.0.0.1:4173/dist/",
    reuseExistingServer: false,
    stdout: "ignore",
    stderr: "pipe",
  },
});
