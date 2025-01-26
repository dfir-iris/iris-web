import { test, expect } from '@playwright/test';
import crypto from 'node:crypto';

test.beforeEach(async({ page }) => {
    await page.goto('/case/assets?cid=1');
});

test('should not be able to create an asset with the same type and value', async ({ page }) => {
    const assetValue = `Asset value - ${crypto.randomUUID()}`;

    await page.getByRole('button', { name: 'Add assets' }).click();
    await page.getByRole('button', { name: 'None' }).click();
    await page.getByRole('listbox').getByRole('option', { name: 'Account', exact: true }).click();
    await page.getByPlaceholder('One asset per line').fill(assetValue);
    await page.getByRole('button', { name: 'Save' }).click();

    await page.getByRole('button', { name: 'Add assets' }).click();
    await page.getByRole('button', { name: 'None' }).click();
    await page.getByRole('listbox').getByRole('option', { name: 'Account', exact: true }).click();
    await page.getByPlaceholder('One asset per line').fill(assetValue);
    await page.getByRole('button', { name: 'Save' }).click();

    await expect(page.getByText('Asset with same value and type already exists')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Save' })).toBeVisible();
});
