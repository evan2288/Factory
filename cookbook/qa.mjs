// Layout QA for both books. Usage: node qa.mjs [--shots]
// Checks every page for: content taller than the page, text or graphics outside the page, clipped text,
// any two lines of text whose glyphs overlap, text touching a graphic it doesn't belong to, graphics
// overlapping each other, glyphs the embedded fonts can't draw, and big empty areas.
import { chromium } from 'playwright';
import path from 'node:path';
import fs from 'node:fs';

const here = path.dirname(new URL(import.meta.url).pathname);
const out = path.join(here, 'out');
const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const shots = process.argv.includes('--shots');
const browser = await chromium.launch({ executablePath: fs.existsSync(exe) ? exe : undefined });
const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 816, height: 1056 } });
let total = 0;

function audit() {
  const issues = [];
  const info = [];
  const fonts = ['40px Anton', '16px "DM Sans"', '24px Caveat'].filter((f) => !document.fonts.check(f));
  if (fonts.length) issues.push(`fonts not loaded: ${fonts.join(', ')}`);
  // Latin subset the embedded fonts cover.
  const ok = /[\u0000-ÿıŒœʻʼˆ˚˜ -⁯€™↑↓−∕﻿�]/u;
  const cv = document.createElement('canvas').getContext('2d');
  const IN = 96;
  const pages = [...document.querySelectorAll('.page')];
  pages.forEach((p, idx) => {
    const no = idx + 1;
    const P = p.getBoundingClientRect();
    const full = p.classList.contains('cover') || p.classList.contains('chapter');
    if (p.scrollHeight > p.clientHeight + 1) issues.push(`p${no}: content ${p.scrollHeight - p.clientHeight}px taller than the page`);
    const visible = (el) => { for (let e = el; e && e !== p; e = e.parentElement) { const s = getComputedStyle(e); if (s.display === 'none' || s.visibility === 'hidden') return false; } return true; };
    const texts = [];
    const tw = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = tw.nextNode())) {
      const raw = node.textContent;
      if (!raw.trim()) continue;
      const el = node.parentElement;
      if (el.closest('svg') || !visible(el)) continue;
      const bad = [...raw].filter((ch) => !ok.test(ch));
      if (bad.length) issues.push(`p${no}: glyphs the fonts lack: ${JSON.stringify(bad.join(''))} in "${raw.trim().slice(0, 40)}"`);
      const cs = getComputedStyle(el);
      let t = raw.trim();
      if (cs.textTransform === 'uppercase') t = t.toUpperCase();
      cv.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
      const m = cv.measureText(t);
      const fa = m.fontBoundingBoxAscent, fd = m.fontBoundingBoxDescent;
      let rot = null;
      for (let e = el; e && e !== p; e = e.parentElement) if (getComputedStyle(e).transform !== 'none' && !e.classList.contains('mini-page')) { rot = e; break; }
      const r = document.createRange();
      r.selectNodeContents(node);
      for (const q of r.getClientRects()) {
        if (q.width < 0.5 || q.height < 0.5) continue;
        const k = q.height / (fa + fd);
        const base = q.top + fa * k;
        texts.push({ el, node, rot, l: q.left, r: q.right, t: base - m.actualBoundingBoxAscent * k, b: base + m.actualBoundingBoxDescent * k, s: t.slice(0, 28) });
      }
    }
    const gfx = [];
    p.querySelectorAll('svg, img, .badge, .deco').forEach((el) => {
      if (el.parentElement.closest('svg') || !visible(el)) return;
      const q = el.getBoundingClientRect();
      if (q.width < 1 || q.height < 1) return;
      const circle = el.classList.contains('badge');
      gfx.push({ el, l: q.left, r: q.right, t: q.top, b: q.bottom, circle, rad: circle ? el.offsetWidth / 2 : 0, s: (el.getAttribute('class') || el.tagName) });
    });
    const inMini = (el) => !!el.closest('.mini-wrap');
    const hit = (a, b) => {
      const ox = Math.min(a.r, b.r) - Math.max(a.l, b.l);
      const oy = Math.min(a.b, b.b) - Math.max(a.t, b.t);
      if (ox <= 1 || oy <= 1) return false;
      for (const [c, x] of [[a, b], [b, a]]) {
        if (!c.circle) continue;
        const cx = (c.l + c.r) / 2, cy = (c.t + c.b) / 2;
        const dx = Math.max(x.l - cx, 0, cx - x.r), dy = Math.max(x.t - cy, 0, cy - x.b);
        if (dx * dx + dy * dy >= (c.rad - 1) ** 2) return false;
      }
      return true;
    };
    for (let i = 0; i < texts.length; i++) {
      const a = texts[i];
      if (a.l < P.left - 1 || a.r > P.right + 1 || a.t < P.top - 1 || a.b > P.bottom + 1) issues.push(`p${no}: text outside the page: "${a.s}"`);
      // Text must stay inside whichever ancestor clips it, and inside its own block's box.
      if (!inMini(a.el)) {
        for (let e = a.el; e && e !== p; e = e.parentElement) {
          const s = getComputedStyle(e);
          if (s.overflow !== 'visible' || s.display !== 'inline') {
            const q = e.getBoundingClientRect();
            const pl = parseFloat(s.paddingLeft) || 0, pr = parseFloat(s.paddingRight) || 0;
            if (a.r > q.right - pr + 1.5 || a.l < q.left + pl - 1.5) issues.push(`p${no}: text spills sideways out of its box: "${a.s}" (${e.className || e.tagName})`);
            if (s.overflow !== 'visible' && (a.b > q.bottom + 1 || a.t < q.top - 1)) issues.push(`p${no}: text clipped: "${a.s}"`);
            break;
          }
        }
      }
      for (let j = i + 1; j < texts.length; j++) {
        const b = texts[j];
        // Lines inside the same rotated box (the cover badge) report inflated rects; the browser stacks them itself.
        if (a.rot && a.rot === b.rot) continue;
        if (hit(a, b)) issues.push(`p${no}: text overlaps text: "${a.s}" / "${b.s}"`);
      }
      for (const g of gfx) if (!g.el.contains(a.el) && hit(a, g)) issues.push(`p${no}: text overlaps graphic ${g.s}: "${a.s}"`);
    }
    for (let i = 0; i < gfx.length; i++) {
      const a = gfx[i];
      if (a.l < P.left - 1 || a.r > P.right + 1 || a.t < P.top - 1 || a.b > P.bottom + 1) issues.push(`p${no}: graphic outside the page: ${a.s}`);
      for (let j = i + 1; j < gfx.length; j++) {
        const b = gfx[j];
        if (!a.el.contains(b.el) && !b.el.contains(a.el) && hit(a, b)) issues.push(`p${no}: graphics overlap: ${a.s} / ${b.s}`);
      }
    }
    // Empty space: lowest ink on the page (ignoring footer) vs the bottom margin.
    if (!full) {
      const content = texts.filter((x) => !x.el.closest('.foot, .num')).map((x) => x.b).concat(gfx.map((g) => g.b));
      const free = (P.bottom - 0.6 * IN) - Math.max(...content);
      if (free > 1.4 * IN) issues.push(`p${no}: ${(free / IN).toFixed(1)}in empty at the bottom`);
      else if (free > 0.9 * IN) info.push(`p${no}: ${(free / IN).toFixed(1)}in free at the bottom`);
      const st = p.querySelector('.band .stats');
      if (st && getComputedStyle(st).display === 'none') info.push(`p${no}: flavour stats hidden (tight page)`);
      const band = p.querySelector('.band');
      if (band) info.push(`band p${no}: ${(band.getBoundingClientRect().height / IN).toFixed(2)}in`);
    }
  });
  return { pages: pages.length, issues, info };
}

for (const [src, tag] of [['unhinged-kitchen.html', 'paid'], ['starter-pack.html', 'free']]) {
  const page = await ctx.newPage();
  await page.goto('file://' + path.join(out, src), { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(400);
  const rep = await page.evaluate(audit);
  const uniq = [...new Set(rep.issues)];
  total += uniq.length;
  console.log(`${tag}: ${rep.pages} pages, ${uniq.length} issues`);
  for (const s of uniq) console.log('  ' + s);
  const bands = rep.info.filter((s) => s.startsWith('band')).map((s) => s.split(': ')[1]);
  if (bands.length) console.log(`  band heights (in): ${bands.join(' ')}`);
  for (const s of rep.info.filter((s) => !s.startsWith('band'))) console.log('  info: ' + s);
  if (shots) {
    const dir = path.join(out, `thumbs-${tag}`);
    fs.rmSync(dir, { recursive: true, force: true });
    fs.mkdirSync(dir, { recursive: true });
    const els = await page.$$('.page');
    for (let i = 0; i < els.length; i++) await els[i].screenshot({ path: path.join(dir, `p${String(i + 1).padStart(2, '0')}.png`) });
  }
  await page.close();
}
await browser.close();
console.log(total ? `TOTAL ISSUES: ${total}` : 'ALL CLEAR');
process.exitCode = total ? 1 : 0;
