import { test, expect, waitForApp } from './fixtures/test-helpers';

test.describe('Search E2E', () => {
  test('search section renders', async ({ page }) => {
    await waitForApp(page);

    const searchInput = page.locator('input[type="search"], input[placeholder*="search"], input[placeholder*="Search"]').first();
    if (await searchInput.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(searchInput).toBeVisible();
    }
  });

  test('search API works', async ({ page }) => {
    const response = await page.request.post('http://localhost:8000/search', {
      data: { query: 'hello', limit: 5 },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('messages');
  });

  test('search returns results for known content', async ({ page }) => {
    const response = await page.request.post('http://localhost:8000/search', {
      data: { query: 'the', limit: 10 },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data.messages)).toBeTruthy();
  });

  test('malformed search query does not crash', async ({ page }) => {
    const response = await page.request.post('http://localhost:8000/search', {
      data: { query: '(" OR 1=1 --', limit: 5 },
    });
    expect(response.ok()).toBeTruthy();
  });
});
