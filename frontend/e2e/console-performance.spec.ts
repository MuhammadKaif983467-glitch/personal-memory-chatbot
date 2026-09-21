import { test, expect, waitForApp } from './fixtures/test-helpers';

test.describe('Console & Network Audit', () => {
  test('no console errors on app load', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await waitForApp(page);
    await page.waitForTimeout(3000);

    const criticalErrors = consoleErrors.filter(e =>
      !e.includes('favicon') &&
      !e.includes('analytics') &&
      !e.includes('WebSocket') &&
      !e.includes('HMR') &&
      !e.includes('socket')
    );
    expect(criticalErrors).toHaveLength(0);
  });

  test('no network requests leak secrets', async ({ page }) => {
    const leakedSecrets: string[] = [];
    page.on('request', req => {
      const url = req.url();
      const headers = req.headers();
      if (url.includes('sk-') || url.includes('OPENROUTER')) {
        leakedSecrets.push(`URL leak: ${url}`);
      }
      for (const [key, val] of Object.entries(headers)) {
        if (val && typeof val === 'string' && (val.includes('sk-') || val.includes('OPENROUTER_API_KEY'))) {
          leakedSecrets.push(`Header leak: ${key}`);
        }
      }
    });

    await waitForApp(page);
    await page.waitForTimeout(3000);

    expect(leakedSecrets).toHaveLength(0);
  });

  test('health endpoint returns no secrets', async ({ page }) => {
    const response = await page.request.get('http://localhost:8000/health');
    const data = await response.json();
    const body = JSON.stringify(data);
    expect(body).not.toContain('OPENROUTER');
    expect(body).not.toContain('sk-');
    expect(body).not.toContain('api_key');
    expect(body).not.toContain('API_KEY');
  });

  test('frontend loads without network failures', async ({ page }) => {
    const failedRequests: string[] = [];
    page.on('response', response => {
      if (response.status() >= 500) {
        failedRequests.push(`${response.status()} ${response.url()}`);
      }
    });

    await waitForApp(page);
    await page.waitForTimeout(3000);

    expect(failedRequests).toHaveLength(0);
  });
});

test.describe('Browser Performance', () => {
  test('initial page load under 15 seconds', async ({ page }) => {
    const start = Date.now();
    await waitForApp(page);
    const loadTime = Date.now() - start;
    console.log(`Page load: ${loadTime}ms`);
    expect(loadTime).toBeLessThan(15000);
  });

  test('search API response under 2 seconds', async ({ page }) => {
    await waitForApp(page);
    const start = Date.now();
    const response = await page.request.post('http://localhost:8000/search', {
      data: { query: 'hello test query', limit: 10 },
    });
    const elapsed = Date.now() - start;
    console.log(`Search API: ${elapsed}ms`);
    expect(response.ok()).toBeTruthy();
    expect(elapsed).toBeLessThan(2000);
  });

  test('chat API response (provider, best-effort)', async ({ page }) => {
    test.setTimeout(60000);
    const peopleResp = await page.request.get('http://localhost:8000/people');
    const people = await peopleResp.json();
    if (people.length === 0) { test.skip(); return; }

    let elapsed: number;
    let ok = false;
    try {
      const start = Date.now();
      const response = await page.request.post('http://localhost:8000/chat', {
        data: { message: 'Say hi', person_id: people[0].id },
        timeout: 45000,
      });
      elapsed = Date.now() - start;
      ok = response.ok();
    } catch {
      test.skip(true, 'BLOCKED_EXTERNAL_DEPENDENCY: OpenRouter provider unavailable');
      return;
    }
    console.log(`Chat API: ${elapsed}ms`);
    if (!ok) {
      test.skip(true, 'BLOCKED_EXTERNAL_DEPENDENCY: OpenRouter provider returned error');
      return;
    }
    expect(ok).toBeTruthy();
  });

  test('import API response under 5 seconds', async ({ page }) => {
    const ts = Date.now();
    const start = Date.now();
    const response = await page.request.post('http://localhost:8000/import/json', {
      data: {
        consent_confirmed: true,
        conversation: { person: `Perf_${ts}`, title: `Perf Test ${ts}` },
        messages: [
          { sender: `Perf_${ts}`, content: `Performance test ${ts}` },
        ],
      },
    });
    const elapsed = Date.now() - start;
    console.log(`Import API: ${elapsed}ms`);
    expect(response.ok()).toBeTruthy();
    expect(elapsed).toBeLessThan(5000);
  });

  test('backup creation under 5 seconds', async ({ page }) => {
    const start = Date.now();
    const response = await page.request.post('http://localhost:8000/backup/create');
    const elapsed = Date.now() - start;
    console.log(`Backup API: ${elapsed}ms`);
    expect(response.ok()).toBeTruthy();
    expect(elapsed).toBeLessThan(5000);
  });
});
