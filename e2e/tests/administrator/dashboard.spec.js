import { test, expect } from '@playwright/test';

test.beforeEach(async({ page }) => {
    await page.goto('/dashboard');
});

test('create case with empty name should present error', async ({ page }) => {
    // FIXME: Should be a button instead of a link
    await page.getByRole('link', { name: 'Create new case'}).click();
    await page.getByRole('button', { name: 'Create' }).click();
    
    // FIXME: Locator should be: page.getByRole('alert', { name: 'Invalid data type' });
    await expect(page.getByText('Invalid data type')).toBeVisible();
});

test('logout should go back to login page', async ({ page }) => {
    await page.getByRole('link', { name: 'administrator' }).click();
    await page.getByRole('link', { name: 'Logout' }).click();

    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible();
})