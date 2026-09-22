import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  reporter: 'line',
  webServer: {
    command: 'npm run dev:demo',
    url: 'http://127.0.0.1:5175',
    reuseExistingServer: false,
  },
  use: {
    baseURL: 'http://127.0.0.1:5175',
    locale: 'ru-RU',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
})
