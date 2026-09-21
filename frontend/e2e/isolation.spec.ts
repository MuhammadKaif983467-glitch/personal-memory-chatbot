import { test, expect } from './fixtures/test-helpers';

test.describe('Project Isolation E2E', () => {
  test('search does not leak across projects', async ({ page }) => {
    const ts = Date.now();

    const projAResp = await page.request.post('http://localhost:8000/projects', {
      data: { name: `IsoA_${ts}` },
    });
    expect(projAResp.ok()).toBeTruthy();
    const projA = await projAResp.json();

    const projBResp = await page.request.post('http://localhost:8000/projects', {
      data: { name: `IsoB_${ts}` },
    });
    expect(projBResp.ok()).toBeTruthy();
    const projB = await projBResp.json();

    const importAResp = await page.request.post('http://localhost:8000/import/json', {
      data: {
        consent_confirmed: true,
        conversation: { person: `IsoA_${ts}`, title: `Iso A ${ts}` },
        messages: [
          { sender: `IsoA_${ts}`, content: `SECRET_A_${ts}_MARKER` },
        ],
        project_id: projA.id,
      },
    });
    expect(importAResp.ok()).toBeTruthy();

    const importBResp = await page.request.post('http://localhost:8000/import/json', {
      data: {
        consent_confirmed: true,
        conversation: { person: `IsoB_${ts}`, title: `Iso B ${ts}` },
        messages: [
          { sender: `IsoB_${ts}`, content: `SECRET_B_${ts}_MARKER` },
        ],
        project_id: projB.id,
      },
    });
    expect(importBResp.ok()).toBeTruthy();

    const searchAResp = await page.request.post('http://localhost:8000/search', {
      data: { query: `SECRET_B_${ts}_MARKER`, project_id: projA.id, limit: 10 },
    });
    expect(searchAResp.ok()).toBeTruthy();
    const searchA = await searchAResp.json();
    expect(searchA.total).toBe(0);

    const searchBResp = await page.request.post('http://localhost:8000/search', {
      data: { query: `SECRET_B_${ts}_MARKER`, project_id: projB.id, limit: 10 },
    });
    expect(searchBResp.ok()).toBeTruthy();
    const searchB = await searchBResp.json();
    expect(searchB.total).toBeGreaterThan(0);
  });
});
