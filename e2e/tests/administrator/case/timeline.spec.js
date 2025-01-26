import { test, expect } from '@playwright/test';
import crypto from 'node:crypto';

test.beforeEach(async({ page }) => {
    await page.goto('/case/timeline?cid=1');
});

test('should be able to add an event', async ({ page }) => {
    const eventTitle = `Event title - ${crypto.randomUUID()}`;
    await page.getByRole('button', { name: 'Add event' }).click();

    await page.getByLabel('Event Title').fill(eventTitle);
    await page.locator('#event_date').fill('2024-09-25');
    await page.getByRole('button', { name: 'Save' }).click();

    await expect(page.getByRole('link', { name: eventTitle })).toBeVisible();
});

test('should be able to update an event', async ({ page }) => {
    const eventTitle = `Event title - ${crypto.randomUUID()}`;
    await page.getByRole('button', { name: 'Add event' }).click();

    await page.getByLabel('Event Title').fill(eventTitle);
    await page.locator('#event_date').fill('2024-09-25');
    await page.getByRole('button', { name: 'Save' }).click();

    await page.getByRole('link', { name: eventTitle }).click();
    const newEventTitle = `Event title - ${crypto.randomUUID()}`;
    await page.getByLabel('Event Title').fill(newEventTitle);
    await page.getByRole('button', { name: 'Update' }).click();

    await expect(page.getByRole('link', { name: newEventTitle })).toBeVisible();
});

test('should be able to delete an event', async ({ page }) => {
    const eventTitle = `Event title - ${crypto.randomUUID()}`;
    await page.getByRole('button', { name: 'Add event' }).click();

    await page.getByLabel('Event Title').fill(eventTitle);
    await page.locator('#event_date').fill('2024-09-25');
    await page.getByRole('button', { name: 'Save' }).click();

    await page.getByRole('link', { name: eventTitle }).click();
    await page.getByRole('button', { name: 'Delete' }).click();

    await expect(page.getByRole('link', { name: eventTitle })).not.toBeVisible();
});