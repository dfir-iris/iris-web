// @ts-check
import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// require('dotenv').config({ path: path.resolve(__dirname, '.env') });

const BROWSERS = ['Chrome', 'Firefox'];
const files = fs.readdirSync('tests', { withFileTypes: true });
const users = files.filter(file => file.isDirectory()).map(file => file.name);

// setup project
let projects = [{
  name: 'setup',
  testMatch: 'auth.setup.js',
}];

for (const browser of BROWSERS) {
  for (const user of users) {
    projects.push({
      name: `${browser}:${user}`,
      use: {
        ...devices[`Desktop ${browser}`],
        storageState: `playwright/.auth/${user}.json`,
      },
      testDir: `./tests/${user}`,
      dependencies: ['setup'],
    })
  }
}

/**
 * @see https://playwright.dev/docs/test-configuration
 */
module.exports = defineConfig({
  testDir: './tests',
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: 'html',
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: 'https://localhost',

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',
    ignoreHTTPSErrors: true,
  },

  /* Configure projects for major browsers */
  projects: projects,

  /* Run your local dev server before starting the tests */
  // webServer: {
  //   command: 'npm run start',
  //   url: 'http://127.0.0.1:3000',
  //   reuseExistingServer: !process.env.CI,
  // },
});

