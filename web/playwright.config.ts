import { defineConfig } from '@playwright/test'

/*
 * UI smoke suite (charter §2/§6): runs against a live `asterism serve`.
 * Default target is the dev default port; override with SMOKE_URL.
 * These are read-only checks — no daemon starts, no inbox actions.
 */
export default defineConfig({
  testDir: './tests',
  timeout: 20_000,
  retries: 0,
  use: {
    baseURL: process.env.SMOKE_URL || 'http://127.0.0.1:8642',
    viewport: { width: 1440, height: 900 },
  },
  reporter: [['list']],
})
