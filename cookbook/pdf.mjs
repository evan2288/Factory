// Renders the two HTML books to PDF with Chromium. Usage: node pdf.mjs
import { chromium } from 'playwright';
import path from 'node:path';
import fs from 'node:fs';

const here = path.dirname(new URL(import.meta.url).pathname);
const out = path.join(here, 'out');
const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const browser = await chromium.launch({ executablePath: fs.existsSync(exe) ? exe : undefined });
const ctx = await browser.newContext({ ignoreHTTPSErrors: true });
for (const [src, dst] of [['unhinged-kitchen.html', 'Unhinged-Kitchen.pdf'], ['starter-pack.html', 'The-Starter-Pack-FREE.pdf']]) {
  const page = await ctx.newPage();
  await page.goto('file://' + path.join(out, src), { waitUntil: 'networkidle' });
  // The @import fonts load after first paint; wait until the display font is really available.
  await page.waitForFunction(() => document.fonts.check('40px Anton') && document.fonts.check('16px "DM Sans"'), null, { timeout: 20000 }).catch(() => console.warn('fonts not confirmed for', src));
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(800);
  const over = await page.evaluate(() => [...document.querySelectorAll('.page')].map((p, i) => [i + 1, p.scrollHeight - p.clientHeight]).filter(([i, d]) => d > 2 && !document.querySelectorAll('.page')[i - 1].classList.contains('cover')));
  console.log(src, 'overflowing pages:', JSON.stringify(over));
  await page.pdf({ path: path.join(out, dst), width: '8.5in', height: '11in', printBackground: true, preferCSSPageSize: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
  const n = await page.evaluate(() => document.querySelectorAll('.page').length);
  console.log(dst, n, 'pages', Math.round(fs.statSync(path.join(out, dst)).size / 1024), 'KB');
  // Preview PNGs of a few pages for checking.
  for (const i of [0, 1, 5, 6, 7]) {
    const el = (await page.$$('.page'))[i];
    if (el) await el.screenshot({ path: path.join(out, `${dst.replace('.pdf', '')}-p${i + 1}.png`), scale: 'css' });
  }
  await page.close();
}
await browser.close();
