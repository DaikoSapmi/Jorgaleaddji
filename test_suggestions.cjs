const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

function setup() {
  const elements = new Map();
  const document = {
    addEventListener() {},
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, { value: '', hidden: false });
      return elements.get(id);
    },
  };
  const context = vm.createContext({ document, window: {}, UI_STRINGS: {}, console, requests: [] });
  const source = fs.readFileSync('static/app.js', 'utf8')
    .replace(/^import .*;\n/m, '')
    .replace(/\ninitApp\(\);\s*$/, '');
  vm.runInContext(source + `
    renderErrors = (errs) => { lastErrors = errs; };
    renderTargetInteractiveView = (text, errs) => { globalThis.visible = text; };
    updateCounts = () => {};
    renderDiff = () => {};
    setStatus = (key) => { globalThis.status = key; };
    fetch = (url, options) => new Promise((resolve, reject) => {
      requests.push({ resolve, reject, text: JSON.parse(options.body).text });
    });
  `, context);
  return { context, elements };
}

test('corrections update visible text and shift remaining repeated words', () => {
  const { context } = setup();
  vm.runInContext(`
    targetEl.value = '  😀 bad bad';
    const errs = divvunOffsetsForBrowser(targetEl.value, [
      {start_index: 4, end_index: 7, error_text: 'bad'},
      {start_index: 8, end_index: 11, error_text: 'bad'}
    ]);
    lastErrors = errs;
    applyDivvunSuggestion(errs[0], 'good');
    applyDivvunSuggestion(lastErrors[0], 'fine');
  `, context);
  assert.equal(context.visible, '  😀 good fine');
  assert.deepEqual(Array.from(context.requests, (request) => request.text), [
    '  😀 good bad', '  😀 good fine',
  ]);
});

test('stale suggestions do not change another occurrence', () => {
  const { context } = setup();
  vm.runInContext(`
    targetEl.value = 'new bad';
    lastErrors = [{start_index: 0, end_index: 3, error_text: 'bad'}];
    applyDivvunSuggestion(lastErrors[0], 'good');
  `, context);
  assert.equal(vm.runInContext('targetEl.value', context), 'new bad');
  assert.equal(context.status, 'suggestionStale');
  assert.equal(context.requests.length, 0);
});

test('old check responses cannot overwrite later corrections', async () => {
  const { context } = setup();
  vm.runInContext(`
    targetEl.value = 'bad bad';
    lastErrors = [
      {start_index: 0, end_index: 3, error_text: 'bad'},
      {start_index: 4, end_index: 7, error_text: 'bad'}
    ];
    applyDivvunSuggestion(lastErrors[0], 'good');
    applyDivvunSuggestion(lastErrors[0], 'fine');
  `, context);
  context.requests[0].resolve({ ok: true, json: async () => ({ errs: [] }) });
  context.requests[1].reject(new Error('offline'));
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(context.visible, 'good fine');
  assert.equal(context.status, 'divvunError');
  assert.equal(vm.runInContext('divvunCheckStale', context), true);
});

test('partial Divvun checks do not mark a completed translation as failed', () => {
  const { context } = setup();
  const partial = vm.runInContext(
    "resultProgress({result_incomplete: false, divvun_check_incomplete: true}, '12.3')", context
  );
  assert.equal(partial.state, 'done');
  assert.equal(partial.detailKey, 'checkIncomplete');
  const incomplete = vm.runInContext(
    "resultProgress({result_incomplete: true, divvun_check_incomplete: true}, '12.3')", context
  );
  assert.equal(incomplete.state, 'error');
  assert.equal(incomplete.detailKey, 'resultIncomplete');
});
