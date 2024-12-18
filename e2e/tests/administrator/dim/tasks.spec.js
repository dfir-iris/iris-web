import { test } from '../../restFixture.js';
import { expect } from '@playwright/test';
import Api from '../../api.js';
import crypto from 'node:crypto';

let api;

test.beforeEach(async ({ page, rest }) => {
    await page.goto('/dim/tasks');
});

test('should be able to consult task info', async ({ page, rest, browserName }) => {
    let response = await rest.get('/manage/modules/list');
    const modules = (await response.json()).data;
    const irisCheckModule = modules.find(module => module.module_human_name === 'IrisCheck');
    response = await rest.post(`/manage/modules/enable/${irisCheckModule.id}`);
    const caseIdentifier = await Api.createCase(rest);
    await rest.delete(`/api/v2/cases/${caseIdentifier}`);

    await page.goto('/dim/tasks');
    // filter 'Case' column with the case identifier
    // TODO should make the more interface testable to be able to use some page.getByRole
    await page.locator('th:nth-child(4) > .form-group > .form-control').fill(caseIdentifier.toString());
    // filter 'Processing module' column with on_postload_case_delete
    // TODO should make the more interface testable to be able to use some page.getByRole
    await page.locator('th:nth-child(5) > .form-group > .form-control').fill('on_postload_case_delete');
    // TODO should make the more interface testable to be able to use some page.getByRole
    await page.locator('td').getByRole('link').click();
    if (browserName === 'chromium') {
        // TODO this click should not be necessary. However, when run on the chromium browser, it seem the first click is ignored
        //      => there is probably a bug in the code to chase
        await page.locator('td').getByRole('link').click();
    }

    await expect(page.locator('#info_dim_task_modal_body')).toContainText('Module name: iris_check_module');
    await expect(page.locator('#info_dim_task_modal_body')).toContainText('Hook name: on_postload_case_delete');
    await expect(page.locator('#info_dim_task_modal_body')).toContainText('User: administrator');
    await expect(page.locator('#info_dim_task_modal_body')).toContainText(`Case ID: ${caseIdentifier}`);
});
