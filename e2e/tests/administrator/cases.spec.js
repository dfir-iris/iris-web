import { test, expect } from '@playwright/test';
import crypto from 'node:crypto';

test.beforeEach(async({ page }) => {
    await page.goto('/case?cid=1');
});

test('should be able to update IOC', async ({ page }) => {
    await page.getByRole('link', { name: 'IOC', exact: true }).click();

    const IocValue = `IOC value - ${crypto.randomUUID()}`;

    await page.getByRole('button', { name: 'Add IOC' }).click();
    await page.getByRole('button', { name: 'None' }).click();
    await page.getByRole('listbox').getByRole('option', { name: 'AS', exact: true }).click();
    await page.getByLabel('IOC Value').fill(IocValue);
    await page.getByRole('button', { name: 'Save' }).click();

    await page.getByRole('link', { name: IocValue }).click();
    const newIocValue = `IOC value - ${crypto.randomUUID()}`;
    await page.getByLabel('IOC Value').fill(newIocValue);
    await page.getByRole('button', { name: 'Update' }).click();

    await expect(page.getByRole('link', { name: newIocValue })).toBeVisible();
});