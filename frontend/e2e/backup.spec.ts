import { test, expect } from './fixtures/test-helpers';

test.describe('Backup E2E (API)', () => {
  test('create backup', async ({ page }) => {
    const response = await page.request.post('http://localhost:8000/backup/create', {
      data: { label: 'e2e_test' },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.valid).toBeTruthy();
    expect(data.size).toBeGreaterThan(0);
    expect(data.message_count).toBeGreaterThanOrEqual(0);
  });

  test('list backups', async ({ page }) => {
    const response = await page.request.get('http://localhost:8000/backup');
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
  });

  test('validate backup', async ({ page }) => {
    const createResponse = await page.request.post('http://localhost:8000/backup/create', {
      data: { label: 'validate_test' },
    });
    const createData = await createResponse.json();

    const validateResponse = await page.request.post('http://localhost:8000/backup/validate', {
      data: { backup_path: createData.path },
    });
    expect(validateResponse.ok()).toBeTruthy();
    const validateData = await validateResponse.json();
    expect(validateData.valid).toBeTruthy();
  });

  test('backup has integrity check', async ({ page }) => {
    const response = await page.request.post('http://localhost:8000/backup/create', {
      data: { label: 'integrity_test' },
    });
    const data = await response.json();
    expect(data.valid).toBeTruthy();
    expect(data.errors).toHaveLength(0);
  });

  test('path traversal is rejected', async ({ page }) => {
    const response = await page.request.post('http://localhost:8000/backup/validate', {
      data: { backup_path: '../../etc/passwd' },
    });
    expect(response.status()).toBe(400);
  });
});
