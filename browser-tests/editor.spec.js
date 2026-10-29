'use strict';
const {test, expect} = require('@playwright/test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {execFileSync} = require('node:child_process');
const {createHash} = require('node:crypto');
const ROOT = path.resolve(__dirname, '..');
const PYTHON = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const CLI = path.join(ROOT, 'teach-me/scripts/graph_editor.py');
const hash = raw => createHash('sha256').update(raw).digest('hex');
const node = (id, extra = {}) => ({id, name: id, statement: 'Statement ' + id, aliases: [], createdAt: '', provenance: [], ...extra});
function baseGraph() {
  return {format: 'teach-me-learning-v1', source_files: [], sessions: [],
    nodes: [node('a', {aliases: ['earlier-a'], createdAt: '2025-01-01', provenance: [{chatId: 'synthetic', messageId: 'm1'}]}), node('b'), node('c'), node('literal', {name: '<img src=x onerror=alert(1)>', statement: '</script><script>alert(2)</script>'})],
    chains: [{id: 'joint', premises: ['a', 'b'], conclusion: 'c', createdAt: '', provenance: []}], warnings: []};
}
const cli = args => JSON.parse(execFileSync(PYTHON, [CLI, ...args], {encoding: 'utf8'}));
let state;
test.beforeEach(async ({page, browser}, testInfo) => {
  const dir = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'teach-me-browser-')));
  const graph = baseGraph();
  const raw = Buffer.from(JSON.stringify(graph, null, 2) + '\n');
  const base = path.join(dir, 'base.json'); const html = path.join(dir, 'editor.html');
  fs.writeFileSync(base, raw); cli(['render', '--input', base, '--output', html]);
  state = {dir, base, raw, graph, baseSHA: hash(raw), requests: [], errors: [], dialogs: [], exports: 0};
  page.on('request', request => state.requests.push(request.url()));
  page.on('pageerror', error => state.errors.push(error.message));
  page.on('dialog', async dialog => { state.dialogs.push(dialog.message()); await dialog.dismiss(); });
  await page.goto(pathToFileURL(html).href);
  await expect(page.getByRole('heading', {name: 'Shape a graph draft'})).toBeVisible();
  console.log(JSON.stringify({project: testInfo.project.name, platform: process.platform, browser_version: browser.version(), document_transport: 'file', synthetic_data: true}));
});
test.afterEach(async () => {
  try {
    expect(state.errors).toEqual([]); expect(state.dialogs).toEqual([]);
    expect(state.requests.filter(url => !url.startsWith('file:') && !url.startsWith('blob:'))).toEqual([]);
    expect(fs.readFileSync(state.base).equals(state.raw)).toBe(true);
  } finally { fs.rmSync(state.dir, {recursive: true, force: true}); }
});
async function draft(page) {
  const wait = page.waitForEvent('download');
  await page.locator('#export-draft').click(); const download = await wait;
  const target = path.join(state.dir, 'download-' + (++state.exports) + '.json');
  await download.saveAs(target);
  const text = fs.readFileSync(target, 'utf8');
  expect(text).toBe(await page.locator('#exported-draft').inputValue());
  return {text, value: JSON.parse(text), target};
}
async function editName(page, name) {
  await page.getByRole('button', {name: 'Edit claim a', exact: true}).click();
  await page.locator('#node-name').fill(name); await page.locator('#node-save').click();
}
async function importText(page, text) {
  await page.locator('#import-draft-text').fill(text); await page.locator('#import-draft').click();
}
async function tabTo(page, target) {
  for (let i = 0; i < 100; i++) {
    if (await target.evaluate(element => element === element.ownerDocument.activeElement)) return;
    await page.keyboard.press('Tab');
  }
  throw new Error('Keyboard could not reach target: ' + await target.getAttribute('id'));
}

test('actual download preserves metadata and AND through CLI check/apply', async ({page}) => {
  await expect(page.locator('img')).toHaveCount(0);
  await expect(page.locator('#graph-cards')).toContainText('<img src=x onerror=alert(1)>');
  await editName(page, 'Revised A');
  await page.locator('#chain-new').click();
  await page.locator('#chain-id').fill('reverse'); await page.locator('#chain-premises').fill('a\nb');
  await page.locator('#chain-conclusion').fill('a'); await page.locator('#chain-save').click();
  const out = await draft(page);
  expect(out.value.patch.upsert_nodes[0]).toEqual({...state.graph.nodes[0], name: 'Revised A'});
  expect(out.value.patch.upsert_chains[0].premises).toEqual(['a', 'b']);
  const check = cli(['check', '--base', state.base, '--draft', out.target]);
  const destination = path.join(state.dir, 'new-graph.json');
  cli(['apply', '--base', state.base, '--draft', out.target, '--expected-draft-sha256', check.draft_sha256, '--output', destination, '--approve']);
  const graph = JSON.parse(fs.readFileSync(destination, 'utf8'));
  expect(graph.nodes[0]).toEqual({...state.graph.nodes[0], name: 'Revised A'});
  expect(graph.chains.find(record => record.id === 'reverse').premises).toEqual(['a', 'b']);
  console.log(JSON.stringify({roundtrip: 'download-check-apply', base_preserved: true, metadata_preserved: true}));
});

test('history branch reset import and atomic refusal preserve staged work', async ({page}) => {
  await expect(page.locator('#undo-draft')).toBeDisabled();
  await editName(page, 'First'); const first = await draft(page);
  await page.locator('#undo-draft').click();
  expect((await draft(page)).value.patch.upsert_nodes).toEqual([]);
  await page.locator('#redo-draft').click(); expect((await draft(page)).value).toEqual(first.value);
  await page.locator('#undo-draft').click(); await editName(page, 'Branch');
  await expect(page.locator('#redo-draft')).toBeDisabled();
  const branch = await draft(page);
  await page.locator('#reset-all').click(); expect((await draft(page)).value.patch.upsert_nodes).toEqual([]);
  await page.locator('#undo-draft').click(); expect((await draft(page)).value).toEqual(branch.value);
  await importText(page, first.text); expect((await draft(page)).value).toEqual(first.value);
  await page.locator('#undo-draft').click(); expect((await draft(page)).value).toEqual(branch.value);
  await page.locator('#redo-draft').click(); expect((await draft(page)).value).toEqual(first.value);
  const before = await page.locator('#exported-draft').inputValue();
  const badBase = JSON.parse(first.text); badBase.base_sha256 = '0'.repeat(64);
  const badMeta = JSON.parse(first.text); badMeta.patch.upsert_nodes[0].provenance = [];
  const dangling = JSON.parse(first.text); dangling.patch.upsert_chains = [{id: 'bad', premises: ['absent'], conclusion: 'a', createdAt: '', provenance: []}];
  const extra = JSON.parse(first.text); extra.extra = true;
  const invalid = ['{', first.text.replace('"version": 1,', '"version": 1, "version": 1,'), JSON.stringify(badBase), JSON.stringify(badMeta), JSON.stringify(dangling), JSON.stringify(extra), ' '.repeat(2097153)];
  for (const text of invalid) {
    await importText(page, text);
    await expect(page.locator('#import-draft-text')).toBeFocused();
    expect(await page.locator('#exported-draft').inputValue()).toBe(before);
    await expect(page.locator('#graph-cards')).toContainText('First');
  }
});

test('history count is bounded and eviction is visible', async ({page}) => {
  for (let i = 0; i < 22; i++) await editName(page, 'Change ' + i);
  await expect(page.locator('#action-status')).toContainText(/histor|oldest|limit|discard|evict/i);
  for (let i = 0; i < 20; i++) {
    await expect(page.locator('#undo-draft')).toBeEnabled(); await page.locator('#undo-draft').click();
  }
  await expect(page.locator('#undo-draft')).toBeDisabled();
  expect((await draft(page)).value.patch.upsert_nodes[0].name).toBe('Change 1');
});

test('keyboard editing focus repair and 390px layout', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await tabTo(page, page.locator('#node-new')); await page.keyboard.press('Enter');
  await expect(page.locator('#node-id')).toBeFocused();
  await page.keyboard.type('keyboard'); await page.keyboard.press('Tab'); await page.keyboard.type('Keyboard claim');
  await page.keyboard.press('Tab'); await page.keyboard.type('A keyboard-created statement.');
  await tabTo(page, page.locator('#node-save')); await page.keyboard.press('Enter');
  await expect(page.locator('#graph-cards')).toContainText('Keyboard claim');
  await tabTo(page, page.locator('#node-delete')); await page.keyboard.press('Enter');
  await expect(page.locator('#node-id')).toBeFocused();
  await page.keyboard.type(' bad '); await tabTo(page, page.locator('#node-save')); await page.keyboard.press('Enter');
  await expect(page.locator('#node-id')).toBeFocused();
  await tabTo(page, page.locator('#import-draft-text')); await page.keyboard.type('{');
  await tabTo(page, page.locator('#import-draft')); await page.keyboard.press('Enter');
  await expect(page.locator('#import-draft-text')).toBeFocused();
  await tabTo(page, page.locator('#reset-all')); await page.keyboard.press('Enter');
  expect(await page.evaluate(() => !!document.activeElement && document.activeElement.tagName !== 'BODY')).toBe(true);
  await tabTo(page, page.locator('#export-draft'));
  const downloaded = page.waitForEvent('download'); await page.keyboard.press('Enter');
  const download = await downloaded; const target = path.join(state.dir, 'keyboard-draft.json'); await download.saveAs(target);
  const check = cli(['check', '--base', state.base, '--draft', target]); expect(check.draft_sha256).toBe(hash(fs.readFileSync(target)));
});
