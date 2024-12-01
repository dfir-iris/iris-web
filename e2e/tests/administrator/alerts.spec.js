import { test } from '../restFixture.js';
import { expect } from '@playwright/test';
import crypto from 'node:crypto';

test.beforeEach(async({ page }) => {
    await page.goto('/alerts');
});

test('should present the alert', async ({ page, rest }) => {
    const alertTitle = `Alert - ${crypto.randomUUID()}`;

    let response = await rest.post('/alerts/add', {
        data: {
            alert_title: alertTitle,
            alert_severity_id: 4,
            alert_status_id: 3,
            alert_customer_id: 1
        }
    });
    await expect(page.getByRole('heading', { name: alertTitle })).toBeVisible();
});