import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './live', workers: 1, timeout: 60000, retries: 1,
  outputDir: './test-results/live',
  use: {baseURL: 'https://lukasmonken.github.io/observatorio-credito-brasil/',
    headless: true, trace: 'retain-on-failure', screenshot: 'only-on-failure'},
});
