import { defineConfig } from '@playwright/test'
import config from './playwright.config'

export default defineConfig({
  ...config,
  testIgnore: [],
  testMatch: '**/*.visual.spec.ts',
  snapshotPathTemplate: '{testDir}/{testFilePath}-snapshots/{arg}{ext}',
  use: { ...config.use, browserName: 'chromium', timezoneId: 'UTC', reducedMotion: 'reduce' },
  expect: { toHaveScreenshot: { animations: 'disabled', maxDiffPixels: 0 } },
})
