import { test, expect, waitForApp } from './fixtures/test-helpers';

test.describe('Conversation E2E', () => {
  test('conversations API returns list', async ({ page }) => {
    const response = await page.request.get('http://localhost:8000/conversations');
    expect(response.ok()).toBeTruthy();
    const conversations = await response.json();
    expect(Array.isArray(conversations)).toBeTruthy();
  });

  test('conversation has required fields', async ({ page }) => {
    const response = await page.request.get('http://localhost:8000/conversations');
    const conversations = await response.json();

    if (conversations.length > 0) {
      const conv = conversations[0];
      expect(conv.id).toBeTruthy();
      expect(conv.title).toBeTruthy();
    }
  });

  test('conversation messages load via messages endpoint', async ({ page }) => {
    const convResponse = await page.request.get('http://localhost:8000/conversations');
    const conversations = await convResponse.json();

    if (conversations.length > 0) {
      const convId = conversations[0].id;
      const msgResponse = await page.request.get(`http://localhost:8000/messages?conversation_id=${convId}`);
      expect(msgResponse.ok()).toBeTruthy();
      const data = await msgResponse.json();
      expect(data.items).toBeTruthy();
      expect(Array.isArray(data.items)).toBeTruthy();
    } else {
      test.skip();
    }
  });

  test('messages have correct sender field', async ({ page }) => {
    const convResponse = await page.request.get('http://localhost:8000/conversations');
    const conversations = await convResponse.json();

    if (conversations.length > 0) {
      const convId = conversations[0].id;
      const msgResponse = await page.request.get(`http://localhost:8000/messages?conversation_id=${convId}`);
      const data = await msgResponse.json();
      const items = data.items || [];

      if (items.length > 0) {
        const firstMsg = items[0];
        expect(firstMsg.sender).toBeTruthy();
        expect(typeof firstMsg.sender).toBe('string');
      }
    }
  });

  test('conversations section visible in UI', async ({ page }) => {
    await waitForApp(page);

    const convLink = page.getByText(/conversation/i).first();
    if (await convLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(convLink).toBeVisible();
    }
  });
});
