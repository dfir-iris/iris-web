import { test, expect } from '@playwright/test';
import crypto from 'node:crypto';

test.beforeEach(async({ page }) => {
    await page.goto('/manage/templates');
});

test('should create report template', async ({ page }) => {
    await page.getByRole('button', { name: 'Add template' }).click();

    const templateName = `The test template name - ${crypto.randomUUID()}`;
    await page.getByLabel('Template name', { exact: true }).fill(templateName);
    await page.getByRole('button', { name: 'Report type' }).click();
    await page.getByRole('listbox').getByRole('option', { name: 'Investigation' }).click();
    await page.getByRole('button', { name: 'Language' }).click();
    await page.getByRole('listbox').getByRole('option', { name: 'French' }).click();

    await page.getByLabel('Template description').fill('description');
    await page.getByLabel('Template file :').fill('Generated report name');
    await page.locator('input[name="file"]').setInputFiles('./data/report.md');

    await page.getByRole('button', { name: 'Save' }).click();

    await expect(page.getByRole('link', { name: templateName })).toBeVisible();
});
