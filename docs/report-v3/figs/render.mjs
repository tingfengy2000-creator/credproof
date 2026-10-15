import { createRequire } from 'node:module';
import { readdirSync } from 'node:fs';
import { join } from 'node:path';
// Resolve playwright from the current working directory (run where it is installed).
const require = createRequire(join(process.cwd(), 'noop.js'));
const { chromium } = require('playwright');
const dir = process.argv[2], out = process.argv[3], only = process.argv[4];
const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
const page = await browser.newPage({ deviceScaleFactor: 2 });
for (const f of readdirSync(dir).filter(x => x.endsWith('.html') && (!only || x.startsWith(only)))) {
  await page.goto('file://' + join(dir, f));
  await page.waitForTimeout(150);
  await page.locator('#fig').screenshot({ path: join(out, f.replace('.html', '.png')) });
  console.log('rendered', f);
}
await browser.close();
