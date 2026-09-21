import { test, expect, waitForApp } from './fixtures/test-helpers';

test.describe('Project Management E2E', () => {
  test('project list renders as select/options', async ({ page }) => {
    await waitForApp(page);

    const select = page.locator('select').first();
    await expect(select).toBeVisible({ timeout: 10000 });
    const options = select.locator('option');
    const count = await options.count();
    expect(count).toBeGreaterThan(0);
  });

  test('default project exists in dropdown', async ({ page }) => {
    await waitForApp(page);

    const option = page.locator('option', { hasText: 'Demo / Regression' }).first();
    await expect(option).toBeAttached({ timeout: 10000 });
  });

  test('can create a new project via API', async ({ page }) => {
    const response = await page.request.post('http://localhost:8000/projects', {
      data: { name: 'E2E Test Project' },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.name).toBe('E2E Test Project');
    expect(data.id).toBeTruthy();
  });

  test('project appears in dropdown after creation', async ({ page }) => {
    await page.request.post('http://localhost:8000/projects', {
      data: { name: 'E2E Visible Project' },
    });

    await waitForApp(page);

    const option = page.locator('option', { hasText: 'E2E Visible Project' }).first();
    await expect(option).toBeAttached({ timeout: 10000 });
  });

  test('can switch projects via dropdown', async ({ page }) => {
    await waitForApp(page);

    const select = page.locator('select').first();
    await expect(select).toBeVisible({ timeout: 10000 });

    const options = select.locator('option');
    const count = await options.count();

    if (count >= 2) {
      const secondValue = await options.nth(1).getAttribute('value');
      if (secondValue) {
        await select.selectOption(secondValue);
        await page.waitForTimeout(1000);
        const selected = await select.inputValue();
        expect(selected).toBe(secondValue);
      }
    } else {
      test.skip();
    }
  });
});
