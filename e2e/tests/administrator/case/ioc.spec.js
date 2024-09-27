import { test, expect } from '@playwright/test';
import crypto from 'node:crypto';

test.beforeEach(async({ page }) => {
    await page.goto('/case/ioc?cid=1');
});

test('should be able to update IOC', async ({ page }) => {
    const iocValue = `IOC value - ${crypto.randomUUID()}`;

    await page.getByRole('button', { name: 'Add IOC' }).click();
    await page.getByRole('button', { name: 'None' }).click();
    await page.getByRole('listbox').getByRole('option', { name: 'AS', exact: true }).click();
    await page.getByLabel('IOC Value').fill(iocValue);
    await page.getByRole('button', { name: 'Save' }).click();

    await page.getByRole('link', { name: iocValue }).click();
    const newIocValue = `IOC value - ${crypto.randomUUID()}`;
    await page.getByLabel('IOC Value').fill(newIocValue);
    await page.getByRole('button', { name: 'Update' }).click();

    await expect(page.getByRole('link', { name: newIocValue })).toBeVisible();
});

test('should not be able to create an IOC with the same type and value', async ({ page }) => {
    const iocValue = `IOC value - ${crypto.randomUUID()}`;

    await page.getByRole('button', { name: 'Add IOC' }).click();
    await page.getByRole('button', { name: 'None' }).click();
    await page.getByRole('listbox').getByRole('option', { name: 'AS', exact: true }).click();
    await page.getByLabel('IOC Value').fill(iocValue);
    await page.getByRole('button', { name: 'Save' }).click();

    await page.getByRole('button', { name: 'Add IOC' }).click();
    await page.getByRole('button', { name: 'None' }).click();
    await page.getByRole('listbox').getByRole('option', { name: 'AS', exact: true }).click();
    await page.getByLabel('IOC Value').fill(iocValue);
    await page.getByRole('button', { name: 'Save' }).click();

    await expect(page.getByText('IOC with same value and type already exists')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Save' })).toBeVisible();
});
