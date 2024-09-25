import { test, expect } from '@playwright/test';

test.beforeEach(async({ page }) => {
    await page.goto('/manage/modules');
});

test('should present the default modules', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'Iris IntelOwl' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'IrisCheck' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'IrisMISP' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'IrisVT' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'IrisWebHooks' })).toBeVisible();

});

test('should filter by hook name', async ({ page }) => {
    await page.locator('#hooks_table_filter').getByLabel('Search:').fill('e_create');

    await expect(page.getByRole('gridcell', { name: 'on_postload_case_create' })).toBeVisible();
});