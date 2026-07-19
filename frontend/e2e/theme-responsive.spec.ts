import { expect, test } from '@playwright/test';

test.describe('theme and responsive application shell', () => {
  test('persists an explicit dark preference and follows accessible menu behavior', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/citizen');

    await page.getByRole('button', { name: 'Giao diện: Theo hệ thống' }).click();
    await page.getByRole('menuitemradio', { name: 'Tối' }).click();

    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await expect.poll(() => page.evaluate(() => localStorage.getItem('ubndai.theme'))).toBe('dark');

    const menuToggle = page.getByRole('button', { name: 'Mở điều hướng' });
    await menuToggle.click();
    await expect(page.getByRole('navigation', { name: 'Điều hướng chính' })).toHaveClass(/open/);
    await page.keyboard.press('Escape');
    await expect(page.getByRole('button', { name: 'Mở điều hướng' })).toBeFocused();

    const widths = await page.evaluate(() => ({ viewport: document.documentElement.clientWidth, content: document.documentElement.scrollWidth }));
    expect(widths.content).toBeLessThanOrEqual(widths.viewport);

    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  });

  test('renders stable light and dark login surfaces', async ({ page }, testInfo) => {
    const isMobile = testInfo.project.name === 'mobile';
    await page.setViewportSize(isMobile ? { width: 390, height: 844 } : { width: 1280, height: 720 });
    await page.addInitScript(theme => localStorage.setItem('ubndai.theme', theme), isMobile ? 'dark' : 'light');
    await page.goto('/citizen');

    await expect(page.getByRole('heading', { name: 'Chuẩn bị hồ sơ đúng ngay từ lần đầu.' })).toBeVisible();
    await expect(page).toHaveScreenshot(`citizen-login-${testInfo.project.name}.png`, { animations: 'disabled' });
  });
});
