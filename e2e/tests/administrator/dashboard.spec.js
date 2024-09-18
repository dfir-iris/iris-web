import { test, expect } from '@playwright/test';

test.use({ storageState: 'playwright/.auth/administrator.json' })

test('create case with empty name should present error', async ({ page }) => {
    await page.goto('/dashboard');
    
    // FIXME: Should be a button instead of a link
    await page.getByRole('link', { name: 'Create new case'}).click();
    await page.getByRole('button', { name: 'Create' }).click();
    
    // FIXME: Locator should be: page.getByRole('alert', { name: 'Invalid data type' });
    await expect(page.getByText('Invalid data type')).toBeVisible();
});
