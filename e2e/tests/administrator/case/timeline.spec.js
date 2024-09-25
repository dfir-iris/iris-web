import { test, expect } from '@playwright/test';
import crypto from 'node:crypto';

test.beforeEach(async({ page }) => {
    await page.goto('/case/timeline?cid=1');
});

test('should be able to add en event', async ({ page }) => {
    const eventTitle = `Event title - ${crypto.randomUUID()}`;
    await page.getByRole('button', { name: 'Add event' }).click();

    await page.getByLabel('Event Title').fill(eventTitle);
    await page.locator('#event_date').fill('2024-09-25');
    await page.getByRole('button', { name: 'Save' }).click();

    await expect(page.getByRole('link', { name: eventTitle })).toBeVisible();
});