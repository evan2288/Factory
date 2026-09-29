// Store assets for CrazyGames: cover screenshots and silent preview-video frames.
// Usage: npm run build && node scripts/assets.mjs <outdir>
// Then: python3 scripts/finish-assets.py <outdir>   (adds the title to covers, encodes videos)
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import fs from 'node:fs';

const out = process.argv[2] || 'assets-out';
fs.mkdirSync(`${out}/frames-land`, { recursive: true });
fs.mkdirSync(`${out}/frames-port`, { recursive: true });
const server = spawn('npx', ['vite', 'preview', '--port', '4176', '--strictPort'], { stdio: 'ignore' });
await new Promise((r) => setTimeout(r, 2500));
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });

async function openLevel(page, level) {
  await page.goto(`http://localhost:4176/?nolock&level=${level}`);
  await page.waitForSelector('#menu:not(.hidden)', { timeout: 20000 });
  await page.evaluate((id) => window.__curfew.startLevel(id), level);
  await page.waitForTimeout(300);
  // Hide HUD text that shouldn't be in covers/videos (cursor, hints, intro banner).
  await page.addStyleTag({ content: '#message,#hint,#crosshair{display:none!important}' });
}

// The hero shot: a corridor in The Block, one patrol sweeping toward the camera, lamp overhead.
async function heroScene(page) {
  await page.evaluate(() => {
    const g = window.__curfew;
    g.enforcers.slice(1).forEach((x) => { x.pos.set(70, 0, 30); x.sync(); x.update = () => {}; });
    const e = g.enforcers[0];
    e.pos.set(27, 0, 17); e.yaw = -Math.PI / 2 + 0.25; e.sync(); e.update = () => {};
    g.player.pos.set(18.5, 0, 17); g.player.yaw = -Math.PI / 2; g.player.pitch = -0.02;
    g.player.keys.add('KeyC');
    g.player.update(0.01);
  });
  await page.waitForTimeout(500);
}

try {
  // Covers.
  for (const [name, w, h] of [['cover-landscape', 1920, 1080], ['cover-portrait', 800, 1200], ['cover-square', 800, 800]]) {
    const page = await browser.newPage({ viewport: { width: w, height: h } });
    await openLevel(page, 'block');
    await page.addStyleTag({ content: '#hud{display:none!important}' });
    await heroScene(page);
    await page.screenshot({ path: `${out}/${name}-raw.png` });
    await page.close();
    console.log('cover', name);
  }

  // Preview video frames: a scripted 16-second sneak past a patrol. Rendered small
  // (software GL in CI is slow) and upscaled/interpolated to 1080p 24fps by finish-assets.py.
  for (const [dir, w, h] of [['frames-land', 640, 360], ['frames-port', 480, 720]]) {
    const page = await browser.newPage({ viewport: { width: w, height: h } });
    await openLevel(page, 'block');
    await page.evaluate(() => {
      const g = window.__curfew;
      g.enforcers.slice(1).forEach((x) => { x.pos.set(70, 0, 30); x.sync(); x.update = () => {}; });
      const e = g.enforcers[0];
      e.pos.set(29, 0, 17); e.yaw = -Math.PI / 2; e.path = []; e.wait = 99; e.sync();
      e.lookAround = function (dt) { this.lookTimer += dt; this.yaw = this.lookBase + Math.sin(this.lookTimer * 0.9) * 0.9; };
      e.lookBase = -Math.PI / 2;
      g.player.pos.set(9, 0, 17); g.player.yaw = -Math.PI / 2; g.player.pitch = 0;
      g.player.setFlashlight(true);
    });
    const FPS = 12;
    const seconds = 16;
    let n = 0;
    for (let f = 0; f < seconds * FPS; f++) {
      const t = f / FPS;
      await page.evaluate((t) => {
        const g = window.__curfew;
        const p = g.player;
        p.keys.clear();
        if (t < 5) { p.keys.add('KeyW'); }                       // walk in with the flashlight
        else if (t < 5.4) { p.setFlashlight(false); }            // kill the light
        else if (t < 9) { p.keys.add('KeyC'); p.keys.add('KeyA'); p.yaw += 0.012; } // crouch, sidestep, turn
        else if (t < 12) { p.keys.add('KeyC'); p.pitch = Math.max(-0.15, p.pitch - 0.004); }
        else if (t < 15) { p.keys.add('ShiftLeft'); p.keys.add('KeyS'); p.yaw -= 0.02; } // sprint away
        else { p.keys.add('KeyC'); }
        g.simulate(1 / 12, 1 / 24);
      }, t);
      await page.screenshot({ path: `${out}/${dir}/f${String(n++).padStart(4, '0')}.png` });
      if (f % 24 === 0) console.log(dir, `${t.toFixed(0)}s`);
    }
    await page.close();
  }
} finally {
  await browser.close();
  server.kill();
}
console.log('done');
