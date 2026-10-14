// Browser check for the CredProof console (PR #8). Read-only: it only issues GETs
// by navigating routes, never clicks a button that posts. Run from any folder in
// which `npm i --no-save playwright@1.56.1` has been executed:
//
//   node <repo>/docs/ui/console-v1/check-console.mjs --base http://127.0.0.1:8765 --out ./console-check
//   options: --channel msedge (Windows, uses installed Edge; default) | chrome | chromium
//            --executable <path to chromium>   --patch <bench patch id>
//
// Writes screenshots, report.pdf and summary.json into --out; exits 1 if any check fails.
import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const require = createRequire(join(process.cwd(), 'noop.js'));
const { chromium } = require('playwright');

const arg = (name, fallback) => { const i = process.argv.indexOf(`--${name}`); return i > 0 ? process.argv[i + 1] : fallback; };
const base = arg('base', 'http://127.0.0.1:8765').replace(/\/$/, '');
const out = resolve(arg('out', 'console-check'));
const channel = arg('channel', process.platform === 'win32' ? 'msedge' : 'chromium');
const executable = arg('executable', null);
const patchId = arg('patch', 'b07-webhook-relay__qwen3-coder-30b__s1__r0');
mkdirSync(out, { recursive: true });

const routes = ['home', 'projects', 'new', 'recheck', 'environment', 'overview', 'patches', 'patches?origin=history',
  `patch/${patchId}`, `report/${patchId}`, 'pipeline', 'ci', 'human-review', 'workbench', 'project-entry', 'method', 'cases', 'mechanism'];
const summary = { base, channel, started_at: new Date().toISOString(), routes: {}, failures: [] };
const fail = (where, what) => summary.failures.push(`${where}: ${what}`);

const launch = executable ? { executablePath: executable } : channel === 'chromium' ? {} : { channel };
const browser = await chromium.launch(launch);
summary.browser = browser.version();

for (const [label, viewport] of [['desktop', { width: 1440, height: 900 }], ['mobile', { width: 390, height: 844 }]]) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  let current = '';
  const log = {};
  const note = (key, value) => { (log[current] ||= { errors: [], writes: [], http: [] })[key].push(value); };
  page.on('console', m => { if (m.type() === 'error') note('errors', m.text()); });
  page.on('pageerror', e => note('errors', `pageerror ${e.message}`));
  page.on('request', r => { if (r.method() !== 'GET') note('writes', `${r.method()} ${r.url()}`); });
  page.on('response', r => { if (r.status() >= 400 && !r.url().endsWith('/favicon.ico')) note('http', `${r.status()} ${r.url()}`); });

  for (const route of (label === 'desktop' ? routes : ['home', 'projects', 'new', 'overview', 'patches', `patch/${patchId}`])) {
    current = `${label} #${route}`;
    log[current] = { errors: [], writes: [], http: [] };
    await page.goto(`${base}/#${route}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(800);
    const facts = await page.evaluate(() => {
      const visible = [...document.querySelectorAll('.view')].filter(v => !v.hidden).map(v => v.dataset.view);
      const result = { visible, title: document.getElementById('page-title')?.textContent?.trim(),
        overflow: document.documentElement.scrollWidth - window.innerWidth,
        // A font counts as installed when it renders differently from both generic fallbacks.
        fonts: (() => { const ctx = document.createElement('canvas').getContext('2d'); const sample = '密证验收报告 CredProof 0123';
          const width = font => { ctx.font = font; return ctx.measureText(sample).width; };
          return Object.fromEntries(['Microsoft YaHei', 'SimSun', 'PingFang SC', 'Noto Sans CJK SC', 'Noto Serif CJK SC', 'Songti SC']
            .map(f => [f, ['monospace', 'serif'].every(g => width(`32px "${f}", ${g}`) !== width(`32px ${g}`))])); })() };
      const matrix = document.getElementById('matrix');
      if (matrix && matrix.offsetParent) {
        // Header spacer cells must sit exactly over each data row's cells.
        const head = [...matrix.querySelectorAll('.cell-spacer')].map(c => Math.round(c.getBoundingClientRect().left));
        const rows = [...matrix.querySelectorAll('.cells')].slice(1).map(r => [...r.querySelectorAll('a.cell')].map(c => Math.round(c.getBoundingClientRect().left)));
        result.matrix = { columns: head.length, rows: rows.length,
          misaligned: rows.reduce((n, r) => n + r.filter((x, i) => Math.abs(x - head[i]) > 1).length + Math.abs(r.length - head.length), 0) };
      }
      return result;
    });
    log[current].facts = facts;
    const expected = { cases: 'workbench', 'human-review': 'projects', mechanism: 'method', ci: 'pipeline' }[route] || route.split(/[/?]/)[0];
    if (!facts.visible.includes(expected)) fail(current, `expected view ${expected}, got ${facts.visible.join(',')}`);
    if (label === 'mobile' && facts.overflow > 0) fail(current, `horizontal overflow ${facts.overflow}px`);
    if (facts.matrix && facts.matrix.misaligned) fail(current, `matrix misaligned cells ${facts.matrix.misaligned}`);
    const file = `${label}-${route.replace(/[^a-z0-9]+/gi, '_').slice(0, 50)}.png`;
    await page.screenshot({ path: join(out, file), fullPage: true });
    log[current].screenshot = file;
  }

  if (label === 'desktop') {
    current = 'desktop print';
    log[current] = { errors: [], writes: [], http: [] };
    await page.goto(`${base}/#report/${patchId}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(800);
    await page.emulateMedia({ media: 'print' });
    const hidden = await page.evaluate(() => ['.sidebar', '.topbar'].every(s => !document.querySelector(s)?.offsetParent));
    if (!hidden) fail(current, 'navigation visible in print layout');
    await page.pdf({ path: join(out, 'report.pdf'), format: 'A4', preferCSSPageSize: true });
    await page.emulateMedia({ media: 'screen', colorScheme: 'dark' });
    await page.goto(`${base}/#overview`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(800);
    await page.screenshot({ path: join(out, 'desktop-overview-dark.png') });
  }
  for (const [where, entry] of Object.entries(log)) {
    summary.routes[where] = entry;
    for (const e of entry.errors) fail(where, `console ${e}`);
    for (const w of entry.writes) fail(where, `non-GET request ${w}`);
    for (const h of entry.http) fail(where, `http ${h}`);
  }
  await context.close();
}
await browser.close();
summary.finished_at = new Date().toISOString();
summary.result = summary.failures.length ? 'FAIL' : 'PASS';
writeFileSync(join(out, 'summary.json'), JSON.stringify(summary, null, 1) + '\n');
console.log(`${summary.result}: ${summary.failures.length} failure(s); browser ${summary.browser}; output ${out}`);
for (const f of summary.failures) console.log('  - ' + f);
process.exit(summary.failures.length ? 1 : 0);
