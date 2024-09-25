import { test, expect } from '@playwright/test';
import crypto from 'node:crypto';

test.beforeEach(async({ page }) => {
    await page.goto('/case/tasks?cid=1');
});

test('should be able to update task', async ({ page }) => {
    const taskTitle = `Task title - ${crypto.randomUUID()}`;

    await page.getByRole('button', { name: 'Add task' }).click();
    await page.getByRole('button', { name: 'Select task status' }).click();
    await page.locator('a').filter({ hasText: 'To do' }).click();
    await page.getByLabel('Task Title').fill(taskTitle);
    await page.getByRole('button', { name: 'Save' }).click();

    await page.getByRole('link', { name: taskTitle }).click();
    const newTaskTitle = `Task title - ${crypto.randomUUID()}`;
    await page.getByLabel('Task title').fill(newTaskTitle);
    await page.getByRole('button', { name: 'Update' }).click();

    await expect(page.getByRole('link', { name: newTaskTitle })).toBeVisible();
});

test('should be able to update task status', async ({ page }) => {
    const taskTitle = `Task title - ${crypto.randomUUID()}`;

    await page.getByRole('button', { name: 'Add task' }).click();
    await page.getByRole('button', { name: 'Select task status' }).click();
    await page.locator('a').filter({ hasText: 'To do' }).click();
    await page.getByLabel('Task Title').fill(taskTitle);
    await page.getByRole('button', { name: 'Save' }).click();

    await expect(page.getByRole('heading', { name: 'Add task' })).not.toBeVisible();

    await page.getByLabel('Search:').fill(taskTitle);

    await page.getByRole('gridcell', { name: 'To do' }).locator('span').click();
    await expect(page.getByRole('gridcell', { name: 'To do' }).getByRole('combobox')).toBeVisible();
    await page.getByRole('gridcell', { name: 'To do' }).getByRole('combobox').selectOption('In progress');
    await page.getByRole('link', { name: 'Confirm' }).click();

    await expect(page.getByRole('gridcell', { name: 'In progress' }).locator('span')).toBeVisible();
});