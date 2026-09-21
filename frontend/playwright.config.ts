import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [['html', { open: 'never' }]],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    actionTimeout: 15000,
    navigationTimeout: 30000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: 'cd ../backend && ../backend/.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000',
      port: 8000,
      reuseExistingServer: true,
      timeout: 30000,
    },
    {
      command: 'npx vite --host 0.0.0.0 --port 5173',
      port: 5173,
      reuseExistingServer: true,
      timeout: 30000,
    },
  ],
});
