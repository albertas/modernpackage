import { expect, test } from '@playwright/test';

test('status page shows healthy and ready', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'modernpackage' })).toBeVisible();
  await expect(page.getByText('healthy')).toBeVisible();
  await expect(page.getByText('ready')).toBeVisible();
});
