import { test, expect } from '@playwright/test';

test('should present initial case', async ({ page }) => {
    await page.goto('/manage/cases');
    await expect(page.getByRole('gridcell', { name: '#1 - Initial Demo', exact: true })).toBeVisible();
});
