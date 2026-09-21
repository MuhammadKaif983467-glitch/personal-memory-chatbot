import { test, expect } from './fixtures/test-helpers';

test.describe('Conversation Summary E2E (API)', () => {
  test('generate summary for conversation', async ({ page }) => {
    const convResp = await page.request.get('http://localhost:8000/conversations');
    const convs = await convResp.json();

    if (convs.length > 0) {
      const convId = convs[0].id;

      const summaryResp = await page.request.post('http://localhost:8000/summaries/generate', {
        data: { conversation_id: convId },
      });
      expect(summaryResp.ok()).toBeTruthy();
      const summary = await summaryResp.json();
      expect(summary.summary).toBeTruthy();
      expect(summary.message_count).toBeGreaterThanOrEqual(0);
    } else {
      test.skip();
    }
  });

  test('get summary for conversation', async ({ page }) => {
    const convResp = await page.request.get('http://localhost:8000/conversations');
    const convs = await convResp.json();

    if (convs.length > 0) {
      const convId = convs[0].id;

      await page.request.post('http://localhost:8000/summaries/generate', {
        data: { conversation_id: convId },
      });

      const getResp = await page.request.get(`http://localhost:8000/summaries/${convId}`);
      expect(getResp.ok()).toBeTruthy();
      const summary = await getResp.json();
      expect(summary.summary).toBeTruthy();
    } else {
      test.skip();
    }
  });

  test('summary does not replace messages', async ({ page }) => {
    const convResp = await page.request.get('http://localhost:8000/conversations');
    const convs = await convResp.json();

    if (convs.length > 0) {
      const convId = convs[0].id;

      const beforeMsgResp = await page.request.get(`http://localhost:8000/conversations/${convId}/messages`);
      const beforeMsgs = await beforeMsgResp.json();
      const beforeCount = (beforeMsgs.messages || beforeMsgs).length;

      await page.request.post('http://localhost:8000/summaries/generate', {
        data: { conversation_id: convId },
      });

      const afterMsgResp = await page.request.get(`http://localhost:8000/conversations/${convId}/messages`);
      const afterMsgs = await afterMsgResp.json();
      const afterCount = (afterMsgs.messages || afterMsgs).length;

      expect(afterCount).toBe(beforeCount);
    } else {
      test.skip();
    }
  });
});
