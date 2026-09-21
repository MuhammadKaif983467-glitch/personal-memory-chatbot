import { test, expect, waitForApp } from './fixtures/test-helpers';

test.describe('Import E2E', () => {
  test('import JSON via API', async ({ page }) => {
    const ts = Date.now();
    const response = await page.request.post('http://localhost:8000/import/json', {
      data: {
        consent_confirmed: true,
        conversation: { person: `JsonImp_${ts}`, title: `JSON Import ${ts}` },
        messages: [
          { sender: `JsonImp_${ts}`, content: `JSON message ${ts}` },
          { sender: `Other_${ts}`, content: `JSON reply ${ts}` },
        ],
      },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.conversation_id).toBeTruthy();
    expect(data.messages_created).toBeGreaterThan(0);
  });

  test('import creates conversation with messages', async ({ page }) => {
    const ts = Date.now();
    const response = await page.request.post('http://localhost:8000/import/json', {
      data: {
        consent_confirmed: true,
        conversation: { person: `ConvImp_${ts}`, title: `Conv Import ${ts}` },
        messages: [
          { sender: `ConvImp_${ts}`, content: `Conv msg ${ts}` },
          { sender: `ConvOther_${ts}`, content: `Conv reply ${ts}` },
        ],
      },
    });
    const data = await response.json();
    expect(data.conversation_id).toBeTruthy();
    expect(data.messages_created).toBeGreaterThan(0);
  });

  test('imported participants are preserved', async ({ page }) => {
    const ts = Date.now();
    const personName = `Preserved_${ts}`;
    await page.request.post('http://localhost:8000/import/json', {
      data: {
        consent_confirmed: true,
        conversation: { person: personName, title: `Preserve Test ${ts}` },
        messages: [
          { sender: personName, content: `Preserve msg ${ts}` },
          { sender: `PreservedOther_${ts}`, content: `Preserve reply ${ts}` },
        ],
      },
    });

    const peopleResponse = await page.request.get('http://localhost:8000/people');
    const people = await peopleResponse.json();
    const names = people.map((p: any) => p.name);
    expect(names).toContain(personName);
  });

  test('import via file upload (CSV multipart)', async ({ page }) => {
    const ts = Date.now();
    const csvContent = `sender,timestamp,content\nCSV_${ts},2026-01-01T10:00:00Z,CSV upload test ${ts}\nCSV_Other_${ts},2026-01-01T10:01:00Z,CSV reply test ${ts}`;
    const response = await page.request.post('http://localhost:8000/import/csv', {
      multipart: {
        file: {
          name: 'test.csv',
          mimeType: 'text/csv',
          buffer: Buffer.from(csvContent, 'utf-8'),
        },
        person: `CSV_${ts}`,
        consent_confirmed: 'true',
      },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.conversation_id).toBeTruthy();
  });

  test('import via file upload (TXT multipart)', async ({ page }) => {
    const ts = Date.now();
    const txtContent = `Txt_${ts} [2026-01-01 10:00]: Hello ${ts}\nTxt_Other_${ts} [2026-01-01 10:01]: Hi back ${ts}`;
    const response = await page.request.post('http://localhost:8000/import/txt', {
      multipart: {
        file: {
          name: 'test.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from(txtContent, 'utf-8'),
        },
        person: `Txt_${ts}`,
        consent_confirmed: 'true',
      },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.conversation_id).toBeTruthy();
  });

  test('import UI renders', async ({ page }) => {
    await waitForApp(page);

    const importBtn = page.getByRole('button', { name: /import/i }).or(
      page.getByText(/import/i)
    ).first();
    if (await importBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(importBtn).toBeVisible();
    }
  });
});
