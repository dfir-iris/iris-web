import { test } from '../../restFixture.js';
import { expect } from '@playwright/test';
import Api from '../../api.js';
import crypto from 'node:crypto';

const _IOC_DEFAULT_ATTRIBUTE_IDENTIFIER = 1;

test.beforeEach(async({ page }) => {
    await page.goto('/case/ioc?cid=1');
});

// TODO should maybe remove all iocs between each tests: there is a risk we reach the pagination limit

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

test('should open IOC editor when IOC description is JSON', async ({ page, rest }) => {
    const caseIdentifier = await Api.createCase(rest);
    const iocValue = `IOC value - ${crypto.randomUUID()}`;
    const iocDescription = JSON.stringify({
        error: '',
        name: 'sampleLookupNumber',
        parameters: {
            add_on: 'telo_cnam',
            caller_name: true,
            carrier: true,
            pstn: '19999999999'
        }
    });

    const pageErrors = [];
    page.on('pageerror', error => pageErrors.push(error.message));

    await rest.post(`/api/v2/cases/${caseIdentifier}/iocs`, {
        data: {
            ioc_type_id: 1,
            ioc_value: iocValue,
            ioc_tlp_id: 2,
            ioc_description: iocDescription,
            ioc_tags: ''
        }
    });

    await page.goto(`/case/ioc?cid=${caseIdentifier}`);
    await page.getByRole('link', { name: iocValue }).click();

    await expect(page.getByRole('button', { name: 'Update' })).toBeVisible();
    expect(pageErrors.filter(error => error.includes('TOOLTIP: Option "content"')).length).toBe(0);
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
    const caseIdentifier = await Api.createCase(rest);
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

test('should be able to update IOC custom attribute', async ({ page, rest }) => {
    const fieldName = 'some_field';
    const defaultValue = 'custom attribute default value';
    await rest.post(`/manage/attributes/update/${_IOC_DEFAULT_ATTRIBUTE_IDENTIFIER}`, {
        data: {
	        attribute_content: `{"tab": {"${fieldName}": {"type": "input_string", "mandatory": false, "value": "${defaultValue}"}}}`,
	        complete_overwrite: false,
	        partial_overwrite: false
        }
    })
    const iocValue = `IOC value - ${crypto.randomUUID()}`;

    await page.getByRole('button', { name: 'Add IOC' }).click();
    await page.getByRole('tab', { name: 'tab' }).click();
    await expect(page.getByText(fieldName)).toBeVisible();
    await expect(page.locator(`#inpstd_1_${fieldName}`)).toHaveValue(defaultValue);

    await rest.post(`/manage/attributes/update/${_IOC_DEFAULT_ATTRIBUTE_IDENTIFIER}`, {
        data: {
	        attribute_content: '{}',
	        complete_overwrite: false,
	        partial_overwrite: false
        }
    })
});
