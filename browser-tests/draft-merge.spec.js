'use strict';
const {test, expect} = require('@playwright/test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {execFileSync, spawnSync} = require('node:child_process');
const {createHash} = require('node:crypto');
const ROOT = path.resolve(__dirname, '..');
const PYTHON = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const MERGE = path.join(ROOT, 'teach-me/scripts/draft_merge.py');
const EDITOR = path.join(ROOT, 'teach-me/scripts/graph_editor.py');
const hash = raw => createHash('sha256').update(raw).digest('hex');
const copy = value => JSON.parse(JSON.stringify(value));
const node = (id, extra = {}) => ({id, name: id, statement: 'Statement ' + id, aliases: [], createdAt: '', provenance: [], ...extra});
const patch = (extra = {}) => ({version: 1, delete_nodes: [], delete_chains: [], upsert_nodes: [], upsert_chains: [], ...extra});
const cli = (script, args) => JSON.parse(execFileSync(PYTHON, [script, ...args], {encoding: 'utf8'}));
let state;

test.beforeEach(async ({page, browser}, testInfo) => {
  state = undefined;
  const dir = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'teach-me-merge-browser-')));
  const graph = {format: 'teach-me-learning-v1', source_files: [], sessions: [],
    nodes: [node('a', {name: 'Premise A', aliases: ['historical-a'], createdAt: '2025-01-02', provenance: [{chatId: 'synthetic', messageId: 'm1'}]}), node('b'), node('c'), node('literal', {name: '<img src=x onerror=alert(1)>', statement: '</script><script>alert(2)</script>'})],
    chains: [{id: 'joint', premises: ['a', 'b'], conclusion: 'c', createdAt: '2025-01-03', provenance: [{chatId: 'synthetic', messageId: 'argument'}]}], warnings: []};
  const raw = Buffer.from(JSON.stringify(graph, null, 2) + '\n');
  const base = path.join(dir, 'base.json');
  const html = path.join(dir, 'editor.html');
  fs.writeFileSync(base, raw);
  state = {dir, graph, base, raw, baseSHA: hash(raw), sourceRaw: new Map([[base, raw]]), requests: [], errors: [], dialogs: []};
  cli(EDITOR, ['render', '--input', base, '--output', html]);
  page.on('request', request => state.requests.push(request.url()));
  page.on('pageerror', error => state.errors.push(error.message));
  page.on('dialog', async dialog => { state.dialogs.push(dialog.message()); await dialog.dismiss(); });
  await page.goto(pathToFileURL(html).href);
  await expect(page.getByRole('heading', {name: 'Shape a graph draft'})).toBeVisible();
  console.log(JSON.stringify({suite: 'draft-merge', project: testInfo.project.name, platform: process.platform, browser_version: browser.version(), document_transport: 'file', synthetic_data: true}));
});

test.afterEach(async () => {
  if (!state) return;
  try {
    for (const [source, raw] of state.sourceRaw) expect(fs.readFileSync(source).equals(raw)).toBe(true);
    expect(state.errors).toEqual([]);
    expect(state.dialogs).toEqual([]);
    expect(state.requests.filter(url => !url.startsWith('file:') && !url.startsWith('blob:'))).toEqual([]);
  } finally { fs.rmSync(state.dir, {recursive: true, force: true}); }
});

function writeJSON(name, value, source = false) {
  const file = path.join(state.dir, name);
  const raw = Buffer.from(JSON.stringify(value, null, 2) + '\n');
  fs.writeFileSync(file, raw);
  if (source) state.sourceRaw.set(file, raw);
  return file;
}
function branches(leftPatch, rightPatch) {
  state.left = writeJSON('left.json', {version: 1, base_sha256: state.baseSHA, patch: leftPatch}, true);
  state.right = writeJSON('right.json', {version: 1, base_sha256: state.baseSHA, patch: rightPatch}, true);
  state.plan = path.join(state.dir, 'merge-plan.json');
  cli(MERGE, ['plan', '--base', state.base, '--left', state.left, '--right', state.right, '--output', state.plan]);
  state.planRaw = fs.readFileSync(state.plan);
  state.planSHA = hash(state.planRaw);
  return JSON.parse(state.planRaw);
}
function decide(choices) {
  return writeJSON('decisions.json', {version: 1, plan_sha256: state.planSHA, choices});
}
function applyArgs(decisions, output, extra = {}) {
  return ['apply', '--base', state.base, '--left', state.left, '--right', state.right,
    '--plan', state.plan, '--expected-plan-sha256', extra.planSHA || state.planSHA,
    '--decisions', decisions, '--expected-decisions-sha256', extra.decisionsSHA || hash(fs.readFileSync(decisions)),
    '--output', output, '--approve'];
}
function applyMerge(choices) {
  const decisions = decide(choices);
  const decisionRaw = fs.readFileSync(decisions);
  const merged = path.join(state.dir, 'merged-draft.json');
  cli(MERGE, applyArgs(decisions, merged));
  expect(fs.readFileSync(state.plan).equals(state.planRaw)).toBe(true);
  expect(fs.readFileSync(decisions).equals(decisionRaw)).toBe(true);
  return {path: merged, text: fs.readFileSync(merged, 'utf8'), value: JSON.parse(fs.readFileSync(merged, 'utf8'))};
}
async function importDownloadApply(page, merged) {
  expect(Object.keys(merged.value).sort()).toEqual(['base_sha256', 'patch', 'version']);
  expect(merged.value.base_sha256).toBe(state.baseSHA);
  await page.locator('#import-draft-text').fill(merged.text);
  await page.locator('#import-draft').click();
  await expect(page.locator('#action-status')).toContainText('Draft imported');
  await expect(page.locator('img')).toHaveCount(0);
  await expect(page.locator('#graph-cards')).toContainText('<img src=x onerror=alert(1)>');
  const waiting = page.waitForEvent('download');
  await page.locator('#export-draft').click();
  const download = await waiting;
  const exported = path.join(state.dir, 'browser-export.json');
  await download.saveAs(exported);
  const text = fs.readFileSync(exported, 'utf8');
  expect(text).toBe(await page.locator('#exported-draft').inputValue());
  expect(JSON.parse(text)).toEqual(merged.value);
  const check = cli(EDITOR, ['check', '--base', state.base, '--draft', exported]);
  expect(check.draft_sha256).toBe(hash(fs.readFileSync(exported)));
  expect(check.semantic_correctness_verified).toBe(false);
  const graphOut = path.join(state.dir, 'applied-graph.json');
  cli(EDITOR, ['apply', '--base', state.base, '--draft', exported, '--expected-draft-sha256', check.draft_sha256, '--output', graphOut, '--approve']);
  expect(fs.readFileSync(state.base).equals(state.raw)).toBe(true);
  console.log(JSON.stringify({suite: 'draft-merge', roundtrip: 'plan-merge-import-download-check-apply', base_preserved: true}));
  return JSON.parse(fs.readFileSync(graphOut, 'utf8'));
}

test('independent claim and AND argument edits merge through actual browser download', async ({page}) => {
  const leftNode = {...copy(state.graph.nodes[0]), statement: 'Left branch revises the claim.'};
  const rightChain = {id: 'reflection', premises: ['a', 'b'], conclusion: 'a', createdAt: '', provenance: []};
  const plan = branches(patch({upsert_nodes: [leftNode]}), patch({upsert_chains: [rightChain]}));
  expect(plan.format).toBe('teach-me-draft-merge-plan-v1');
  expect(plan.conflicts).toEqual([]);
  expect(plan.automatic.nodes).toEqual([{id: 'a', record: leftNode}]);
  expect(plan.automatic.chains).toEqual([{id: 'reflection', record: rightChain}]);
  const merged = applyMerge([]);
  const graph = await importDownloadApply(page, merged);
  expect(graph.nodes.find(record => record.id === 'a')).toEqual(leftNode);
  expect(graph.chains.find(record => record.id === 'joint')).toEqual(state.graph.chains[0]);
  expect(graph.chains.find(record => record.id === 'reflection')).toEqual(rightChain);
  await expect(page.locator('#graph-cards')).toContainText(' AND ');
});

test('explicit conflict choice preserves one full record and is undoable after import', async ({page}) => {
  const leftNode = {...copy(state.graph.nodes[0]), statement: 'Chosen left statement.'};
  const rightNode = {...copy(state.graph.nodes[0]), name: 'Unchosen right name'};
  const plan = branches(patch({upsert_nodes: [leftNode]}), patch({upsert_nodes: [rightNode]}));
  expect(plan.conflicts).toHaveLength(1);
  expect(plan.conflicts[0]).toEqual({kind: 'node', id: 'a', reason: 'both-edited', base: state.graph.nodes[0], left: leftNode, right: rightNode});
  const merged = applyMerge([{kind: 'node', id: 'a', choose: 'left'}]);
  const graph = await importDownloadApply(page, merged);
  expect(graph.nodes.find(record => record.id === 'a')).toEqual(leftNode);
  expect(graph.nodes.find(record => record.id === 'a').name).toBe('Premise A');
  await page.locator('#undo-draft').click();
  await expect(page.locator('#pending-summary')).toContainText('No changes staged');
  await page.locator('#redo-draft').click();
  await expect(page.locator('#graph-cards')).toContainText('Chosen left statement.');
  await expect(page.locator('#graph-cards')).not.toContainText('Unchosen right name');
});

test('review hash missing choices and foreign output refuse without changing staged work', async ({page}) => {
  const leftNode = {...copy(state.graph.nodes[0]), name: 'Left choice'};
  const rightNode = {...copy(state.graph.nodes[0]), name: 'Right choice'};
  const plan = branches(patch({upsert_nodes: [leftNode]}), patch({upsert_nodes: [rightNode]}));
  expect(plan.conflicts).toHaveLength(1);
  const decisions = decide([{kind: 'node', id: 'a', choose: 'left'}]);
  const output = path.join(state.dir, 'refused-draft.json');
  let result = spawnSync(PYTHON, [MERGE, ...applyArgs(decisions, output, {planSHA: '0'.repeat(64)})], {encoding: 'utf8'});
  expect(result.status).toBe(2);
  expect(fs.existsSync(output)).toBe(false);
  const missing = writeJSON('missing-decisions.json', {version: 1, plan_sha256: state.planSHA, choices: []});
  result = spawnSync(PYTHON, [MERGE, ...applyArgs(missing, output)], {encoding: 'utf8'});
  expect(result.status).toBe(2);
  expect(fs.existsSync(output)).toBe(false);
  fs.writeFileSync(output, 'FOREIGN OUTPUT');
  result = spawnSync(PYTHON, [MERGE, ...applyArgs(decisions, output)], {encoding: 'utf8'});
  expect(result.status).toBe(2);
  expect(fs.readFileSync(output, 'utf8')).toBe('FOREIGN OUTPUT');
  expect(fs.readFileSync(state.plan).equals(state.planRaw)).toBe(true);
  await expect(page.locator('#pending-summary')).toContainText('No changes staged');
  await expect(page.locator('#graph-cards')).not.toContainText('Left choice');
  await expect(page.locator('#graph-cards')).not.toContainText('Right choice');
});
