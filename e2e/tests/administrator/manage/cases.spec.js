import { test, expect } from '@playwright/test';

test.beforeEach(async({ page }) => {
    await page.goto('/manage/cases');
});

test('should present initial case', async ({ page }) => {
    await expect(page.getByRole('gridcell', { name: '#1 - Initial Demo', exact: true })).toBeVisible();
});
