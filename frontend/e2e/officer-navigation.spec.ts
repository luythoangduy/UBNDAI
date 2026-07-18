import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('ubndai.officer.access_token', 'e2e-token'));
  await page.route('**/api/v1/officer-dashboard/**', route => route.fulfill({ json: { success: true, data: route.request().url().includes('summary') ? { total: 3, completed: 1, in_process: 1, caution: 1 } : [] } }));
  await page.route('**/api/v1/applications*', route => route.fulfill({ json: { success: true, data: [] } }));
});

test('officer dashboard and applications share one navigation shell', async ({ page }) => {
  await page.goto('/officer/');
  await expect(page.getByRole('heading', { name: 'Tổng quan' })).toBeVisible();
  await page.getByRole('link', { name: 'Hồ sơ', exact: true }).click();
  await expect(page).toHaveURL(/\/officer\/applications/);
  await expect(page.getByRole('heading', { name: 'Hồ sơ', exact: true })).toBeVisible();
  await expect(page.getByText('Không có hồ sơ phù hợp')).toBeVisible();
});
