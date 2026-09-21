import { test as base, expect, type Page } from '@playwright/test';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const API_URL = process.env.VITE_API_URL || BACKEND_URL;

export const test = base.extend<{
  apiPage: Page;
}>({
  apiPage: async ({}, use) => {
    const page = await base.newPage();
    await use(page);
    await page.close();
  },
});

export { expect };

export async function apiGet(path: string): Promise<any> {
  const resp = await fetch(`${API_URL}${path}`);
  if (!resp.ok) throw new Error(`API GET ${path} failed: ${resp.status}`);
  return resp.json();
}

export async function apiPost(path: string, body?: any): Promise<any> {
  const resp = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) throw new Error(`API POST ${path} failed: ${resp.status}`);
  return resp.json();
}

export async function apiDelete(path: string): Promise<any> {
  const resp = await fetch(`${API_URL}${path}`, { method: 'DELETE' });
  if (!resp.ok) throw new Error(`API DELETE ${path} failed: ${resp.status}`);
  return resp.json();
}

export async function resetTestDb(): Promise<void> {
  try {
    await fetch(`${API_URL}/health`);
  } catch {
    // Backend not running
  }
}

export async function waitForApp(page: Page): Promise<void> {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(2000);
}

export async function createProject(page: Page, name: string): Promise<void> {
  const createBtn = page.locator('button', { hasText: /new project|create project|add project/i });
  if (await createBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await createBtn.click();
    const input = page.locator('input[placeholder*="project"], input[type="text"]').first();
    await input.fill(name);
    const submitBtn = page.locator('button[type="submit"], button', { hasText: /create|save|ok/i }).first();
    await submitBtn.click();
    await page.waitForTimeout(1000);
  }
}
