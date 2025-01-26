import { test as base } from '@playwright/test';
import fs from 'node:fs';
import dotenv from 'dotenv';

const _API_URL = 'http://127.0.0.1:8000';

export const test = base.extend({
  rest: async ({ playwright }, use) => {
    // Set up the fixture.
    const envFile = fs.readFileSync('../.env');
    const env = dotenv.parse(envFile);

    const apiContext = await playwright.request.newContext({
        baseURL: _API_URL,
        extraHTTPHeaders: {
            'Authorization': `Bearer ${env.IRIS_ADM_API_KEY}`,
            'Content-Type': 'application/json'
        },
    });

    // Use the fixture value in the test.
    await use(apiContext);

    // Clean up the fixture.
    await apiContext.dispose();
  },
});
