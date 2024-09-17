import { test, expect } from '@playwright/test';

test('successfully loads', async ({ page }) => {
    await page.goto('/dashboard');
    
    // FIXME: Should be a button instead of a link
    await page.getByRole('link', { name: 'Create new case'}).click();
    await page.getByRole('button', { name: 'Create' }).click();
    
    // FIXME: Locator should be: page.getByRole('alert', { name: 'Invalid data type' });
    await expect(page.getByText('Invalid data type')).toBeVisible();
});


test('should be able to open "Add customer" modal', async ({ page }) => {
    await page.goto('/manage/customers');
    await page.getByRole('button', { name: 'Add customer' }).click();
    await expect(page.getByRole('heading', { name: 'Add customer' })).toBeVisible()
});

