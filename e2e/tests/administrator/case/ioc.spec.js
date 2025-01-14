import { test } from '../../restFixture.js';
import { expect } from '@playwright/test';
import crypto from 'node:crypto';

test.beforeEach(async({ page }) => {
    await page.goto('/case/ioc?cid=1');
});

test('should be able to update IOC', async ({ page }) => {
    const iocValue = `IOC value - ${crypto.randomUUID()}`;

    await page.getByRole('button', { name: 'Add IOC' }).click();
    await page.getByRole('button', { name: 'None' }).click();
    await page.getByRole('listbox').getByRole('option', { name: 'AS', exact: true }).click();
    await page.getByLabel('IOC Value *').fill(iocValue);
    await page.getByRole('button', { name: 'Save' }).click();

    await page.getByRole('link', { name: iocValue }).click();
    const newIocValue = `IOC value - ${crypto.randomUUID()}`;
    await page.getByLabel('IOC Value *').fill(newIocValue);
    await page.getByRole('button', { name: 'Update' }).click();

    await expect(page.getByRole('link', { name: newIocValue })).toBeVisible();
});

test('should not be able to create an IOC with the same type and value', async ({ page }) => {
    const iocValue = `IOC value - ${crypto.randomUUID()}`;

    await page.getByRole('button', { name: 'Add IOC' }).click();
    await page.getByRole('button', { name: 'None' }).click();
    await page.getByRole('listbox').getByRole('option', { name: 'AS', exact: true }).click();
    await page.getByLabel('IOC Value *').fill(iocValue);
    await page.getByRole('button', { name: 'Save' }).click();

    await page.getByRole('button', { name: 'Add IOC' }).click();
    await page.getByRole('button', { name: 'None' }).click();
    await page.getByRole('listbox').getByRole('option', { name: 'AS', exact: true }).click();
    await page.getByLabel('IOC Value *').fill(iocValue);
    await page.getByRole('button', { name: 'Save' }).click();

    await expect(page.getByText('IOC with same value and type already exists')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Save' })).toBeVisible();
});

test('should paginate the IOCs', async ({ page, rest }) => {
    const caseName = `Case - ${crypto.randomUUID()}`;

    // TODO maybe should remove cases between each tests (like in the backend tests)
    let response = await rest.post('/api/v2/cases', {
        data: {
            case_name: caseName,
            case_description: 'Case description',
            case_customer: 1,
            case_soc_id: ''
        }
    });
    const caseIdentifier = (await response.json()).case_id;
    for (let i = 0; i < 11; i++) {
        await rest.post(`/api/v2/cases/${caseIdentifier}/iocs`, {
            data: {
                ioc_type_id: 1,
                ioc_value: `IOC value - ${crypto.randomUUID()}`,
                ioc_tlp_id: 2,
                ioc_description: 'rewrw',
                ioc_tags: ''
            }
        })
    }

    await page.goto(`/case/ioc?cid=${caseIdentifier}`);
    await expect(page.getByRole('link', { name: '2', exact: true })).toBeVisible();
});