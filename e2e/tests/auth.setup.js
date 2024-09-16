import { test as setup } from '@playwright/test';
import path from 'path';

const authFile = path.join(__dirname, '../playwright/.auth/user.json');

const username = "administrator";
const password = "MySuperAdminPassword!";


setup('authenticate', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('textbox', { name: 'Username' }).fill(username);
    await page.getByRole('textbox', { name: 'Password' }).fill(password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    // FIXME: It should be: await page.waitForURL('/dashboard'); No wildcard.
    // Wait until the page receives the cookies.
    await page.waitForURL('/dashboard*');
    await page.context().storageState({ path: authFile });
});