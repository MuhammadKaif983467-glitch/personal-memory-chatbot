import { test, expect, waitForApp } from './fixtures/test-helpers';

test.describe('Smoke Test', () => {
  test('application launches and renders main UI', async ({ page }) => {
    await waitForApp(page);

    const title = await page.title();
    expect(title).toBeTruthy();

    const body = page.locator('body');
    await expect(body).toBeVisible();

    const errors: string[] = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await page.waitForTimeout(2000);

    const jsErrors = errors.filter(e =>
      !e.includes('ResizeObserver') &&
      !e.includes('Non-Error promise rejection')
    );
    expect(jsErrors).toHaveLength(0);
  });

  test('backend health check returns 200', async ({ page }) => {
    const response = await page.request.get('http://localhost:8000/health');
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.status).toBe('ok');
  });

  test('frontend dev server returns 200', async ({ page }) => {
    const response = await page.request.get('http://localhost:5173/');
    expect(response.ok()).toBeTruthy();
  });
});
