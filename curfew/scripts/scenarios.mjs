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

const parkAll = `window.__curfew.enforcers.forEach((x) => { x.pos.set(-50, 0, -50); x.sync(); x.update = () => {}; });`;

async function open(page, level) {
  await page.goto(`http://localhost:4174/?nolock&level=${level}`);
  await page.waitForSelector('#menu:not(.hidden)', { timeout: 15000 });
  await page.waitForTimeout(300);
  await page.evaluate((id) => window.__curfew.startLevel(id), level);
  await page.waitForTimeout(300);
}

try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => m.type() === 'error' && !/crazygames|sdk|Failed to load resource/i.test(m.text()) && errors.push(m.text()));

  // 0. Menu renders the level list and the loading screen is gone.
  await page.goto('http://localhost:4174/?nolock');
  await page.waitForSelector('#menu:not(.hidden)', { timeout: 15000 });
  await page.waitForTimeout(500);
  check((await page.$$('#levels .level')).length === 5, 'menu lists five levels');
  await page.screenshot({ path: `${out}/0-menu.png` });

  // 1. Ambient visibility without flashlight, near a hanging light (The Block).
  await open(page, 'block');
  await page.evaluate(() => {
    const g = window.__curfew;
    g.enforcers.forEach((e) => { e.pos.set(70, 0, 30); e.sync(); e.update = () => {}; });
    g.player.pos.set(19, 0, 11); g.player.yaw = Math.PI / 2; g.player.pitch = -0.05;
  });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${out}/a-ambient.png` });

  // 2. An enforcer patrolling toward you in a corridor.
  await open(page, 'block');
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
  await open(page, 'block');
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
  check(await page.isHidden('#continue'), 'no continue offer without a checkpoint');
  await page.screenshot({ path: `${out}/d-caught.png` });

  // 4. Crouching behind a crate in the dark is not detected quickly.
  await page.click('#again');
  await page.waitForTimeout(300);
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
  check(await page.evaluate(() => !!window.__curfew.player.hidden), 'E next to a locker hides you');
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

  // 6. Collect parts, checkpoint, escape.
  await page.evaluate(parkAll);
  for (let i = 0; i < 3; i++) {
    await page.evaluate((i) => { const g = window.__curfew; const it = g.items[i]; g.player.pos.set(it.group.position.x, 0, it.group.position.z); }, i);
    await page.evaluate(() => window.__curfew.simulate(0.1));
    await page.evaluate(parkAll);
  }
  check((await page.evaluate(() => window.__curfew.parts)) === 3, 'three radio parts collected');
  check((await page.evaluate(() => window.__curfew.enforcers.length)) === 5, 'a reinforcement spawns per part');
  check(!!(await page.evaluate(() => window.__curfew.checkpoint)), 'a checkpoint is saved on pickup');
  await page.evaluate(() => { const g = window.__curfew; const h = g.world.hatch.pos; g.player.pos.set(h.x + 3, 0, h.z); g.player.yaw = Math.PI / 2; g.player.pitch = -0.4; });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${out}/f-hatch.png` });
  await page.evaluate(() => { const g = window.__curfew; const h = g.world.hatch.pos; g.player.pos.set(h.x, 0, h.z); g.simulate(0.1); });
  await page.waitForTimeout(800);
  check((await page.evaluate(() => window.__curfew.state)) === 'ended', 'reaching the hatch with 3 parts wins');
  check(await page.isVisible('#next'), 'win screen offers the next level');
  await page.screenshot({ path: `${out}/g-win.png` });
  const unlocked = await page.evaluate(() => JSON.parse(localStorage.getItem('curfew-save-v1')).unlocked);
  check(unlocked >= 3, `escaping level 2 unlocks level 3 (unlocked=${unlocked})`);

  // 7. Checkpoint continue after being caught.
  await page.click('#next');
  await page.waitForTimeout(400);
  check((await page.evaluate(() => window.__curfew.def.id)) === 'watch', 'Next level starts Under Watch');
  await page.evaluate(parkAll);
  await page.evaluate(() => { const g = window.__curfew; const it = g.items[0]; g.player.pos.set(it.group.position.x, 0, it.group.position.z); g.simulate(0.1); });
  await page.evaluate(parkAll);
  const cp = await page.evaluate(() => ({ parts: window.__curfew.parts, cp: !!window.__curfew.checkpoint }));
  check(cp.parts === 1 && cp.cp, 'part picked up on level 3 with checkpoint');
  await page.evaluate(() => { const g = window.__curfew; g.enforcers[0].update = undefined; delete g.enforcers[0].update; g.enforcers[0].pos.copy(g.player.pos); g.enforcers[0].state = 'chase'; g.enforcers[0].sync(); g.simulate(0.2); });
  await page.waitForTimeout(1200);
  check((await page.evaluate(() => window.__curfew.state)) === 'ended' && await page.isVisible('#continue'), 'caught after a checkpoint offers Continue');
  await page.screenshot({ path: `${out}/h-continue.png` });
  await page.click('#continue');
  await page.waitForTimeout(500);
  const rest = await page.evaluate(() => ({ s: window.__curfew.state, parts: window.__curfew.parts, live: window.__curfew.items.filter((i) => !i.taken).length }));
  check(rest.s === 'playing' && rest.parts === 1 && rest.live === 2, `continue restores parts and remaining items (${JSON.stringify(rest)})`);

  // 8. Cameras: standing in a camera's cone raises an alarm that sends patrols.
  await page.evaluate(parkAll);
  const cam = await page.evaluate(() => {
    const g = window.__curfew;
    const c = g.cameras[0];
    const e = g.enforcers[0];
    delete e.update; e.pos.set(c.pos.x + 12, 0, c.pos.z); e.state = 'patrol'; e.detection = 0; e.sync();
    // Stand 4m in front of the camera, in its mounted direction, flashlight on.
    c.phase = 0; c.yaw = c.baseYaw;
    g.player.pos.set(c.pos.x + Math.sin(c.baseYaw) * 4, 0, c.pos.z + Math.cos(c.baseYaw) * 4);
    g.player.setFlashlight(true);
    let alarm = 0;
    const orig = c.update.bind(c);
    c.update = (dt, t, ctx) => { c.yaw = c.baseYaw; orig(dt, 0, ctx); c.yaw = c.baseYaw; c.head.rotation.y = c.yaw; };
    for (let i = 0; i < 80 && !alarm; i++) { g.simulate(0.1); if (c.cooldown > 0) alarm = 1; }
    return { alarm, es: e.state };
  });
  check(cam.alarm === 1 && cam.es === 'search', `camera alarm sends the patrol searching (${JSON.stringify(cam)})`);
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${out}/i-camera.png` });

  // 9. Lockdown: exit blocked until the key opens the doors.
  await open(page, 'lockdown');
  await page.evaluate(parkAll);
  const before = await page.evaluate(() => ({ key: window.__curfew.hasKey, solid: window.__curfew.level.cells[9][30] }));
  check(!before.key && before.solid === 'D', 'level 4 starts with sealed doors');
  await page.evaluate(() => { const g = window.__curfew; const k = g.keys[0]; g.player.pos.set(k.group.position.x, 0, k.group.position.z); g.simulate(0.1); });
  const after = await page.evaluate(() => ({ key: window.__curfew.hasKey, cell: window.__curfew.level.cells[9][30], opening: window.__curfew.world.doors[0].opening }));
  check(after.key && after.cell === '+' && after.opening, `key opens the doors (${JSON.stringify(after)})`);
  await page.evaluate(() => { const g = window.__curfew; g.player.pos.set(g.world.doors[1].mesh.position.x - 3, 0, g.world.doors[1].mesh.position.z); g.player.yaw = -Math.PI / 2; });
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${out}/j-door.png` });

  // 10. Night Shift: a new part appears after each pickup and there is no hatch.
  await open(page, 'night');
  await page.evaluate(parkAll);
  for (let i = 0; i < 3; i++) {
    await page.evaluate(() => { const g = window.__curfew; const it = g.items.find((x) => !x.taken); g.player.pos.set(it.group.position.x, 0, it.group.position.z); g.simulate(0.1); });
    await page.evaluate(parkAll);
  }
  const night = await page.evaluate(() => ({ parts: window.__curfew.parts, live: window.__curfew.items.filter((i) => !i.taken).length, hatch: !!window.__curfew.world.hatch, en: window.__curfew.enforcers.length }));
  check(night.parts === 3 && night.live === 1 && night.en === 6, `Night Shift keeps spawning parts and patrols (${JSON.stringify(night)})`);

  // 11. Readability at the smallest supported size.
  const small = await browser.newPage({ viewport: { width: 800, height: 450 } });
  await small.goto('http://localhost:4174/?nolock');
  await small.waitForSelector('#menu:not(.hidden)', { timeout: 15000 });
  await small.waitForTimeout(400);
  await small.screenshot({ path: `${out}/k-menu-800x450.png` });
  await small.evaluate(() => window.__curfew.startLevel('ground'));
  await small.waitForTimeout(1500);
  await small.screenshot({ path: `${out}/l-hud-800x450.png` });
  await small.close();
} finally {
  await browser.close();
  server.kill();
}
console.log(errors.length ? `PAGE ERRORS:\n${errors.join('\n')}` : 'no page errors');
process.exit(failures || errors.length ? 1 : 0);
