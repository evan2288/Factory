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
  await page.evaluate((id) => { window.__curfew.startLevel(id); window.__curfew.freeze = true; }, level);
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
      // A patrol that sweeps and walks but can never see or hear the player: pure choreography.
      // It crosses the far end of the corridor (x=31) between z=13 and z=21, sweeping at each end.
      window.THREE = { Vector3: g.player.pos.constructor };
      e.pos.set(31, 0, 13); e.yaw = e.lookBase = Math.PI; e.path = []; e.wait = 1.5; e.sync();
      e.visibility = () => 0; e.hear = () => {};
      e.pickPatrolTarget = function () { this.goTo(new THREE.Vector3(31, 0, this.pos.z < 17 ? 21 : 13)); this.wait = 1.5; };
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
        const e = g.enforcers[0];
        if (t < 3) { p.keys.add('KeyW'); }                         // walk in with the flashlight
        else if (t < 3.5) { p.setFlashlight(false); }              // kill the light: the beam ahead is enough
        else if (t < 6) { p.keys.add('KeyC'); p.keys.add('KeyW'); } // creep forward crouched
        else if (t < 11) { p.keys.add('KeyC'); e.detection = Math.min(0.85, e.detection + 0.015); p.yaw += Math.sin(t * 2) * 0.003; } // hold still, tension rises
        else if (t < 14.5) { p.keys.add('ShiftLeft'); p.keys.add('KeyS'); p.yaw += 0.03; e.detection = 0.3; } // sprint back and turn
        else { p.keys.add('KeyC'); e.detection = 0; }
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
