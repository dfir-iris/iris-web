import { test, expect } from '@playwright/test';

test.beforeEach(async({ page }) => {
    await page.goto('/manage/customers');
});

test('should be able to open "Add customer" modal', async ({ page }) => {
    await page.goto('/manage/customers');
    await page.getByRole('button', { name: 'Add customer' }).click();
    await expect(page.getByRole('heading', { name: 'Add customer' })).toBeVisible()
});
