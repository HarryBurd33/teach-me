'use strict';
const {defineConfig, devices} = require('@playwright/test');
module.exports = defineConfig({
  testDir: './browser-tests', timeout: 45000, globalTimeout: 240000,
  fullyParallel: false, workers: 1, retries: 0, forbidOnly: !!process.env.CI,
  reporter: [['list'], ['json', {outputFile: 'browser-results.json'}]],
  use: {acceptDownloads: true, trace: 'off', screenshot: 'only-on-failure'},
  projects: [
    {name: 'chromium', use: {...devices['Desktop Chrome']}},
    {name: 'firefox', use: {...devices['Desktop Firefox']}},
    {name: 'webkit', use: {...devices['Desktop Safari']}}
  ]
});
