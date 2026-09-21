import { test, expect } from './fixtures/test-helpers';

test.describe('Memory Relationships E2E (API)', () => {
  test('create memory relationship', async ({ page }) => {
    const mem1Resp = await page.request.post('http://localhost:8000/memories', {
      data: {
        person_id: 1,
        content: 'Rel test A',
        memory_type: 'fact',
      },
    });
    const mem1 = await mem1Resp.json();

    const mem2Resp = await page.request.post('http://localhost:8000/memories', {
      data: {
        person_id: 1,
        content: 'Rel test B',
        memory_type: 'fact',
      },
    });
    const mem2 = await mem2Resp.json();

    const relResp = await page.request.post('http://localhost:8000/memory-relationships', {
      data: {
        source_memory_id: mem1.id,
        target_memory_id: mem2.id,
        relationship_type: 'supports',
      },
    });
    expect(relResp.ok()).toBeTruthy();
    const rel = await relResp.json();
    expect(rel.relationship_type).toBe('supports');
  });

  test('self-relationship is rejected', async ({ page }) => {
    const memResp = await page.request.post('http://localhost:8000/memories', {
      data: {
        person_id: 1,
        content: 'Self rel test',
        memory_type: 'fact',
      },
    });
    const mem = await memResp.json();

    const relResp = await page.request.post('http://localhost:8000/memory-relationships', {
      data: {
        source_memory_id: mem.id,
        target_memory_id: mem.id,
        relationship_type: 'supports',
      },
    });
    expect(relResp.status()).toBe(400);
  });

  test('get relationships for memory', async ({ page }) => {
    const mem1Resp = await page.request.post('http://localhost:8000/memories', {
      data: { person_id: 1, content: 'Get rel A', memory_type: 'fact' },
    });
    const mem1 = await mem1Resp.json();

    const mem2Resp = await page.request.post('http://localhost:8000/memories', {
      data: { person_id: 1, content: 'Get rel B', memory_type: 'fact' },
    });
    const mem2 = await mem2Resp.json();

    await page.request.post('http://localhost:8000/memory-relationships', {
      data: {
        source_memory_id: mem1.id,
        target_memory_id: mem2.id,
        relationship_type: 'related_to',
      },
    });

    const relsResp = await page.request.get(`http://localhost:8000/memory-relationships/${mem1.id}`);
    expect(relsResp.ok()).toBeTruthy();
    const rels = await relsResp.json();
    expect(Array.isArray(rels)).toBeTruthy();
  });
});
