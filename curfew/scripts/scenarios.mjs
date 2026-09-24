// Scripted checks of core mechanics in a real browser, with screenshots.
// Usage: npm run build && node scripts/scenarios.mjs <outdir>
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';

const out = process.argv[2] || '.';
const server = spawn('npx', ['vite', 'preview', '--port', '4174', '--strictPort'], { stdio: 'ignore' });
await new Promise((r) => setTimeout(r, 2500));
const errors = [];
let failures = 0;
const check = (ok, msg) => { console.log(ok ? 'PASS' : 'FAIL', msg); if (!ok) failures++; };
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  await page.goto('http://localhost:4174/?nolock');
  await page.waitForTimeout(1200);
  await page.click('#play');
  await page.waitForTimeout(300);

  // 1. Ambient visibility without flashlight, near a hanging light.
  await page.evaluate(() => {
    const g = window.__curfew;
    g.enforcers.forEach((e) => { e.pos.set(70, 0, 30); e.sync(); e.update = () => {}; });
    g.player.pos.set(19, 0, 11); g.player.yaw = Math.PI / 2; g.player.pitch = -0.05;
  });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${out}/a-ambient.png` });

  // 2. An enforcer patrolling toward you in a corridor.
  await page.reload();
  await page.waitForTimeout(1200);
  await page.click('#play');
  await page.evaluate(() => {
    const g = window.__curfew;
    const e = g.enforcers[0];
    g.enforcers.slice(1).forEach((x) => { x.pos.set(70, 0, 30); x.sync(); x.update = () => {}; });
    e.pos.set(26, 0, 17); e.yaw = -Math.PI / 2; e.sync(); e.update = () => {};
    g.player.pos.set(19, 0, 17); g.player.yaw = -Math.PI / 2; g.player.pitch = 0;
  });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${out}/b-enforcer.png` });

  // 3. Detection: stand in an enforcer's beam and get chased and caught.
  await page.reload();
  await page.waitForTimeout(1200);
  await page.click('#play');
  await page.evaluate(() => {
    const g = window.__curfew;
    g.enforcers.slice(1).forEach((x) => { x.pos.set(70, 0, 30); x.sync(); x.update = () => {}; });
    const e = g.enforcers[0];
    e.pos.set(26, 0, 17); e.yaw = e.lookBase = -Math.PI / 2; e.path = []; e.wait = 99; e.sync();
    g.player.pos.set(20, 0, 17); g.player.yaw = -Math.PI / 2;
  });
  const st = await page.evaluate(() => {
    const g = window.__curfew;
    for (let i = 0; i < 60 && g.enforcers[0].state !== 'chase'; i++) g.simulate(0.1);
    return g.enforcers[0].state;
  });
  check(st === 'chase', `enforcer notices a player standing in his beam (state=${st})`);
  await page.screenshot({ path: `${out}/c-chase.png` });
  await page.evaluate(() => window.__curfew.simulate(8));
  check((await page.evaluate(() => window.__curfew.state)) === 'ended', 'standing still while chased gets you caught');
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${out}/d-caught.png` });

  // 4. Crouching behind a crate in the dark is not detected quickly.
  await page.click('#again');
  await page.evaluate(() => {
    const g = window.__curfew;
    g.enforcers.slice(1).forEach((x) => { x.pos.set(70, 0, 30); x.sync(); x.update = () => {}; });
    const e = g.enforcers[0];
    // Crate at cell (18,9); enforcer north of it looking south, player south of it crouched.
    e.pos.set(37, 0, 13); e.yaw = 0; e.path = []; e.wait = 99; e.lookAround = () => {}; e.sync();
    g.player.pos.set(37, 0, 20.6); g.player.yaw = Math.PI; g.player.keys.add('KeyC');
  });
  await page.evaluate(() => window.__curfew.simulate(3));
  const hid = await page.evaluate(() => ({ s: window.__curfew.enforcers[0].state, d: window.__curfew.enforcers[0].detection }));
  check(hid.s === 'patrol' && hid.d === 0, `crouched behind crate stays hidden (${JSON.stringify(hid)})`);

  // 5. Hiding in a locker unseen keeps you safe even when a patrol walks past.
  await page.evaluate(() => {
    const g = window.__curfew;
    g.player.keys.clear();
    const l = g.world.lockers.find((k) => k.cell.x === 13 && k.cell.z === 1);
    g.player.pos.copy(l.exit);
    g.player.yaw = Math.atan2(-(l.pos.x - l.exit.x), -(l.pos.z - l.exit.z));
    window.__locker = l;
  });
  await page.keyboard.press('KeyE');
  await page.waitForTimeout(300);
  const hidden = await page.evaluate(() => !!window.__curfew.player.hidden);
  check(hidden, 'E next to a locker hides you');
  await page.screenshot({ path: `${out}/e-locker.png` });
  await page.evaluate(() => {
    const g = window.__curfew;
    const e = g.enforcers[0];
    delete e.lookAround;
    e.wait = 0; e.state = 'patrol'; e.detection = 0;
    e.pos.set(window.__locker.exit.x + 6, 0, window.__locker.exit.z); e.goTo(window.__locker.exit.clone().setX(window.__locker.exit.x - 6)); e.sync();
  });
  await page.evaluate(() => window.__curfew.simulate(6));
  const safe = await page.evaluate(() => ({ g: window.__curfew.state, s: window.__curfew.enforcers[0].state }));
  check(safe.g === 'playing' && safe.s === 'patrol', `unseen locker hide is safe (${JSON.stringify(safe)})`);
  await page.keyboard.press('KeyE');
  check(!(await page.evaluate(() => window.__curfew.player.hidden)), 'E again leaves the locker');

  // 6. Collect parts and escape.
  await page.evaluate(() => {
    const g = window.__curfew;
    g.enforcers.forEach((x) => { x.pos.set(70, 0, 30); x.sync(); x.update = () => {}; });
  });
  for (let i = 0; i < 3; i++) {
    await page.evaluate((i) => { const g = window.__curfew; const it = g.items[i]; g.player.pos.set(it.group.position.x, 0, it.group.position.z); }, i);
    await page.evaluate(() => window.__curfew.simulate(0.1));
  }
  check((await page.evaluate(() => window.__curfew.parts)) === 3, 'three radio parts collected');
  check((await page.evaluate(() => window.__curfew.enforcers.length)) === 5, 'a reinforcement spawns per part');
  await page.evaluate(() => { const g = window.__curfew; const h = g.world.hatch.pos; g.enforcers.forEach((x) => { x.pos.set(70, 0, 30); x.update = () => {}; }); g.player.pos.set(h.x + 3, 0, h.z); g.player.yaw = Math.PI / 2; g.player.pitch = -0.4; });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${out}/f-hatch.png` });
  await page.evaluate(() => { const g = window.__curfew; const h = g.world.hatch.pos; g.player.pos.set(h.x, 0, h.z); g.simulate(0.1); });
  await page.waitForTimeout(800);
  check((await page.evaluate(() => window.__curfew.state)) === 'ended', 'reaching the hatch with 3 parts wins');
  await page.screenshot({ path: `${out}/g-win.png` });
} finally {
  await browser.close();
  server.kill();
}
console.log(errors.length ? `PAGE ERRORS:\n${errors.join('\n')}` : 'no page errors');
process.exit(failures || errors.length ? 1 : 0);
