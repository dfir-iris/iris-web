import { test, expect } from '@playwright/test';

test.beforeEach(async({ page }) => {
    await page.goto('/manage/customers');
});

test('should present initial client', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'IrisInitialClient' })).toBeVisible();
});

test('should be able to open "Add customer" modal', async ({ page }) => {
    await page.getByRole('button', { name: 'Add customer' }).click();
    await expect(page.getByRole('heading', { name: 'Add customer' })).toBeVisible()
});

test('should present IrisInitialClient associated cases', async ({ page }) => {
    await page.getByRole('link', { name: 'IrisInitialClient' }).click();

    await page.getByRole('button', { name: ' Cases' }).click();
    await expect(page.getByRole('gridcell', { name: '#1 - Initial Demo' })).toBeVisible();
});