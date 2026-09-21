import { test, expect, waitForApp } from './fixtures/test-helpers';

test.describe('People E2E', () => {
  test('people list renders', async ({ page }) => {
    await waitForApp(page);

    const response = await page.request.get('http://localhost:8000/people');
    expect(response.ok()).toBeTruthy();
    const people = await response.json();
    expect(Array.isArray(people)).toBeTruthy();
    expect(people.length).toBeGreaterThan(0);
  });

  test('people have required fields', async ({ page }) => {
    const response = await page.request.get('http://localhost:8000/people');
    const people = await response.json();

    if (people.length > 0) {
      const person = people[0];
      expect(person.id).toBeTruthy();
      expect(person.name).toBeTruthy();
      expect(typeof person.name).toBe('string');
    }
  });

  test('participant names are not generic Assistant/User', async ({ page }) => {
    const response = await page.request.get('http://localhost:8000/people');
    const people = await response.json();

    for (const person of people) {
      expect(person.name).not.toBe('Assistant');
      expect(person.name).not.toBe('User');
    }
  });

  test('people appear in list after JSON import', async ({ page }) => {
    await page.request.post('http://localhost:8000/import/json', {
      data: {
        consent_confirmed: true,
        conversation: { person: 'E2EPerson_A', title: 'People Test' },
        messages: [
          { sender: 'E2EPerson_A', content: 'Hello from A' },
          { sender: 'E2EPerson_B', content: 'Hello from B' },
        ],
      },
    });

    await waitForApp(page);

    const response = await page.request.get('http://localhost:8000/people');
    const people = await response.json();
    const names = people.map((p: any) => p.name);
    expect(names).toContain('E2EPerson_A');
    expect(names).toContain('E2EPerson_B');
  });
});
