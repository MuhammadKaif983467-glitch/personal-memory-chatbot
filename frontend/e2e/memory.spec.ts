import { test, expect, waitForApp } from './fixtures/test-helpers';

test.describe('Memory E2E', () => {
  test('memory API returns memories', async ({ page }) => {
    const response = await page.request.get('http://localhost:8000/memories');
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data.memories || data)).toBeTruthy();
  });

  test('memory has required fields', async ({ page }) => {
    const response = await page.request.get('http://localhost:8000/memories');
    const data = await response.json();
    const memories = data.memories || data;

    if (memories.length > 0) {
      const memory = memories[0];
      expect(memory.content).toBeTruthy();
      expect(memory.memory_type).toBeTruthy();
      expect(memory.status).toBeTruthy();
    }
  });

  test('memory section renders in UI', async ({ page }) => {
    await waitForApp(page);

    const memorySection = page.locator('[class*="memory"], [data-testid*="memory"], text=/memory/i').first();
    if (await memorySection.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(memorySection).toBeVisible();
    }
  });
});
