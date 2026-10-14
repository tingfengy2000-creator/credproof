// End-to-end browser check for the product workspace (docs/ui/PRODUCT-API.md).
// Unlike console-v1/check-console.mjs this script WRITES: it creates intakes and
// reviews, runs real isolated checks, records a test-labelled approval, exports
// and rechecks. Run it only against a disposable workspace started with
//   python -m agent_pilot.launch --workspace <copy> --demo --mode recheck --port 8765
// from a folder where `npm i --no-save playwright@1.56.1` has been executed:
//
//   node <repo>/docs/ui/product-v1/check-product.mjs --base http://127.0.0.1:8765 \
//     --out ./product-check --sample <folder with a small Python project> --fixed <fixed tool.py>
//   options: --channel msedge (Windows default) | chrome | chromium   --executable <chromium path>
//
// --sample: a project folder WITHOUT credproof.toml (tests/ + one entry module).
// --fixed:  the repaired material-assistant entry used for the revision step
//           (docs/reusable-tool-safety/acceptance/20261010-human-review/public-evidence/workspace/runs/human-review/*/versions/v001/project/tool.py).
// Writes screenshots and summary.json into --out; exits 1 if any check fails.
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const require = createRequire(join(process.cwd(), 'noop.js'));
const { chromium } = require('playwright');
const arg = (name, fallback) => { const i = process.argv.indexOf(`--${name}`); return i > 0 ? process.argv[i + 1] : fallback; };
const base = arg('base', 'http://127.0.0.1:8765').replace(/\/$/, '');
const out = resolve(arg('out', 'product-check'));
const sample = arg('sample', null);
const fixed = arg('fixed', null);
const channel = arg('channel', process.platform === 'win32' ? 'msedge' : 'chromium');
const executable = arg('executable', null);
mkdirSync(out, { recursive: true });
const summary = { base, started_at: new Date().toISOString(), steps: {}, failures: [] };
const fail = (where, what) => { summary.failures.push(`${where}: ${what}`); console.error(`FAIL ${where}: ${what}`); };
const check = (where, ok, what) => { if (!ok) fail(where, what); return ok; };

const browser = await chromium.launch(executable ? { executablePath: executable } : channel === 'chromium' ? {} : { channel });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
const page = await context.newPage();
const errors = [];
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', e => errors.push(String(e)));
const shot = async name => page.screenshot({ path: join(out, `${name}.png`), fullPage: true });
const idle = () => page.waitForFunction(() => !document.body.classList.contains('is-busy'), null, { timeout: 180000 });
const go = async hash => { await page.goto(`${base}/#${hash}`); await idle(); await page.waitForTimeout(300); };
const banner = async () => (await page.locator('#error-banner').isVisible()) ? await page.locator('#error-banner').innerText() : '';

// 1. Home: story, version switch, binding simulation.
await go('home');
await page.waitForTimeout(3600); // let the single load animation finish
await shot('01-home');
await page.click('[data-story-version="v001"]');
check('home', (await page.locator('#story-evidence .verdict-tag').innerText()) === 'PASS', 'v001 tab does not show PASS');
await page.click('[data-story-change="config"]');
check('home', (await page.locator('#story-outcome').innerText()).includes('409'), 'binding change does not explain 409');
await page.locator('#stage-4').screenshot({ path: join(out, '02-home-stage4.png') });
await page.locator('#stage-5').screenshot({ path: join(out, '03-home-stage5.png') });

// 2. Example project: intake -> start -> real check (FAIL) -> revise -> check (PASS) -> approve -> export.
await go('new');
await shot('04-new-source');
await page.click('[data-example="material-assistant"]');
await page.waitForURL(/#new\/[0-9a-f]{32}/); await idle();
check('example-intake', await page.locator('#config-ok').isVisible(), 'example config not valid');
await shot('05-new-config-example');
await page.click('#config-start');
await page.waitForURL(/#project\/[0-9a-f]{32}/); await idle();
const projectUrl = page.url();
await shot('06-project-new');
await page.click('#project-check'); await idle();
const first = await page.locator('#project-evidence .verdict-tag').innerText().catch(() => '');
summary.steps.example_first_check = first;
check('example-check', first === 'FAIL', `original example verdict ${first} (expected FAIL); banner: ${await banner()}`);
await shot('07-project-fail');
if (fixed) {
  await page.fill('#project-code', readFileSync(fixed, 'utf8'));
  await page.fill('#revise-reason', '改用固定访问组件，跳转时抛出 HTTPError，不输出凭据');
  await page.click('#project-revise'); await idle();
  check('revise', (await page.locator('#project-meta').innerText()).includes('v001'), `revision not created; banner: ${await banner()}`);
  await page.click('#project-check'); await idle();
  const second = await page.locator('#project-evidence .verdict-tag').innerText().catch(() => '');
  summary.steps.example_revised_check = second;
  check('revised-check', second === 'PASS', `revised verdict ${second}; banner: ${await banner()}`);
  await shot('08-project-pass');
  await page.fill('#decide-reason', '浏览器端到端功能测试：审阅差异后采纳');
  await page.check('#decide-test');
  await page.click('#decide-approve'); await idle();
  check('approve', (await page.locator('#project-states').innerText()).includes('已采纳'), `approval not recorded; banner: ${await banner()}`);
  const [sarif] = await Promise.all([page.waitForEvent('download'), page.click('[data-report="sarif"]')]);
  await sarif.saveAs(join(out, 'credproof.sarif'));
  const sarifJson = JSON.parse(readFileSync(join(out, 'credproof.sarif'), 'utf8'));
  check('sarif', sarifJson.version === '2.1.0', 'SARIF download is not 2.1.0');
  const [bundle] = await Promise.all([page.waitForEvent('download'), page.click('#export-adopted')]);
  const bundlePath = join(out, 'credproof-adopted-review.zip');
  await bundle.saveAs(bundlePath);
  await shot('09-project-approved');

  // 3. Recheck the exported bundle in a new directory.
  await go('recheck');
  await page.setInputFiles('#recheck-file', bundlePath); await idle();
  const verdict = await page.locator('#recheck-seal').innerText().catch(() => '');
  summary.steps.recheck = verdict;
  check('recheck', verdict.includes('通过'), `recheck seal ${verdict}; banner: ${await banner()}`);
  await shot('10-recheck');
}

// 4. A user project without configuration: folder upload -> wizard -> check.
if (sample) {
  await go('new');
  await page.fill('#upload-label', '报表下载工具');
  await page.setInputFiles('#pick-folder', sample);
  await page.waitForURL(/#new\/[0-9a-f]{32}/, { timeout: 60000 }); await idle();
  await shot('11-wizard-detected');
  await page.check('#cfg-require-read');
  if (!(await page.isChecked('#cfg-service'))) await page.check('#cfg-service');
  await page.fill('#cfg-prefix', '/api');
  await page.check('#cfg-require-cred');
  await page.fill('#cfg-env', 'REPORT_API_TOKEN');
  // Replace the pre-filled blank scenario with the two templates.
  await page.click('[data-add-scenario="normal"]');
  await page.click('[data-add-scenario="redirect"]');
  await page.click('[data-remove-scenario="0"]');
  check('wizard', (await page.locator('.scenario').count()) === 2, 'scenario templates not applied');
  await page.click('#config-save'); await idle();
  const errorsText = await page.locator('#config-errors').innerText();
  check('wizard', await page.locator('#config-ok').isVisible(), `wizard config invalid: ${errorsText} ${await banner()}`);
  await shot('12-wizard-valid');
  await page.click('#config-start');
  await page.waitForURL(/#project\/[0-9a-f]{32}/); await idle();
  await page.click('#project-check'); await idle();
  const verdict = await page.locator('#project-evidence .verdict-tag').innerText().catch(() => '');
  summary.steps.sample_check = verdict;
  check('sample-check', ['FAIL', 'PASS', 'UNKNOWN'].includes(verdict), `no verdict for uploaded project; banner: ${await banner()}`);
  await shot('13-sample-checked');
}

// 5. Lists, environment, mobile.
await go('projects'); await shot('14-projects');
await go('environment'); await shot('15-environment');
await context.close();
const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
const mpage = await mobile.newPage();
mpage.on('pageerror', e => errors.push(String(e)));
for (const [name, hash] of [['16-mobile-home', 'home'], ['17-mobile-project', projectUrl.split('#')[1]]]) {
  await mpage.goto(`${base}/#${hash}`);
  await mpage.waitForFunction(() => !document.body.classList.contains('is-busy'), null, { timeout: 60000 });
  await mpage.waitForTimeout(3600);
  const overflow = await mpage.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check(name, overflow <= 1, `horizontal overflow ${overflow}px`);
  await mpage.screenshot({ path: join(out, `${name}.png`), fullPage: true });
}
await browser.close();
summary.console_errors = errors;
if (errors.length) fail('console', errors.slice(0, 5).join(' | '));
summary.finished_at = new Date().toISOString();
writeFileSync(join(out, 'summary.json'), JSON.stringify(summary, null, 2));
console.log(JSON.stringify({ failures: summary.failures, steps: summary.steps }, null, 2));
process.exit(summary.failures.length ? 1 : 0);
