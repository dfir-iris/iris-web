import { test, expect } from '@playwright/test';

test.beforeEach(async({ page }) => {
    await page.goto('/manage/modules');
});

test('should present some default modules', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'Iris IntelOwl' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'IrisCheck' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'IrisMISP' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'IrisVT' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'IrisWebHooks' })).toBeVisible();
});
