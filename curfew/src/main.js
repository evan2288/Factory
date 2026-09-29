import * as THREE from 'three';
import { parseLevel, toCell, toWorld, unlockDoors } from './level-data.js';
import { LEVELS, NIGHT_SHIFT, byId } from './levels.js';
import { buildWorld, spawnItems, spawnItem } from './world.js';
import { Player } from './player.js';
import { Enforcer } from './enforcer.js';
import { SecurityCamera } from './camera.js';
import { Sound } from './audio.js';
import { openCells } from './grid.js';
import * as sdk from './sdk.js';
import * as store from './save.js';

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const NO_LOCK = params.has('nolock'); // for automated testing without pointer lock

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;
$('game').appendChild(renderer.domElement);

const camera = new THREE.PerspectiveCamera(72, window.innerWidth / window.innerHeight, 0.05, 70);
const sound = new Sound();

const game = {
  state: 'menu',
  def: LEVELS[0],
  levelIndex: 0,
  level: null,
  scene: null,
  world: null,
  player: null,
  enforcers: [],
  cameras: [],
  items: [],
  keys: [],
  hasKey: false,
  parts: 0,
  difficulty: 1,
  time: 0,
  spotted: 0,
  sirenAt: 30,
  locked: false,
  checkpoint: null,
  hints: null,
};
window.__curfew = game;

const settings = store.load().settings;

function shuffle(a) {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function disposeScene(scene) {
  scene?.traverse((o) => {
    o.geometry?.dispose();
    const mats = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
    mats.forEach((m) => { m.map?.dispose(); m.dispose(); });
  });
}

// ---- Runs -------------------------------------------------------------------

function partsNeeded() {
  return game.def.endless ? Infinity : game.def.partsNeeded;
}

function newRun(def = game.def) {
  game.def = def;
  game.levelIndex = LEVELS.indexOf(def);
  disposeScene(game.scene);
  const scene = new THREE.Scene();
  scene.add(camera);
  camera.clear();
  game.scene = scene;
  game.level = parseLevel(def.map);
  game.world = buildWorld(scene, game.level);
  game.player = new Player(camera, game.level);
  const spots = shuffle([...game.level.spawns.items]);
  game.items = spawnItems(scene, spots.slice(0, def.endless ? 1 : def.partsNeeded));
  game.spareSpots = spots.slice(def.endless ? 1 : def.partsNeeded);
  game.keys = game.world.keys;
  game.hasKey = !game.level.spawns.doors.length;
  game.difficulty = def.difficulty;
  game.enforcers = game.level.spawns.enforcers.map((c) => new Enforcer(scene, game.level, c, game.difficulty));
  game.cameras = game.level.spawns.cameras.map((c) => new SecurityCamera(scene, game.level, c));
  game.parts = 0;
  game.time = 0;
  game.spotted = 0;
  game.sirenAt = 25 + Math.random() * 30;
  game.checkpoint = null;
  game.hints = def.tutorial && !store.load().seenTutorial ? tutorialHints() : null;
  $('danger').style.opacity = 0;
  $('eye-fill').style.width = '0%';
  $('locker-view').classList.add('hidden');
  $('message').style.opacity = 0;
  $('hint').style.opacity = 0;
  updateObjective();
  game.player.applyCamera(0);
  sdk.reportProgress(campaignProgress());
}

function campaignProgress() {
  const s = store.load();
  return Math.min(100, ((s.unlocked - 1) / LEVELS.length) * 100);
}

// A reinforcement arrives each time you grab a part, as far from you as possible.
function spawnReinforcement() {
  const far = farOpenCell(12);
  if (!far) return;
  game.enforcers.push(new Enforcer(game.scene, game.level, far, game.difficulty));
}

function farOpenCell(minDist) {
  const p = game.player.pos;
  const pc = { x: toCell(p.x), z: toCell(p.z) };
  return openCells(game.level)
    .filter((c) => Math.hypot(c.x - pc.x, c.z - pc.z) > minDist)
    .sort(() => Math.random() - 0.5)[0];
}

// Night Shift: a new part appears somewhere far away after each pickup.
function spawnNextPart() {
  const p = game.player.pos;
  const pc = { x: toCell(p.x), z: toCell(p.z) };
  let spot = game.spareSpots.find((c) => Math.hypot(c.x - pc.x, c.z - pc.z) > 8);
  if (spot) game.spareSpots = game.spareSpots.filter((c) => c !== spot);
  else spot = farOpenCell(10);
  if (!spot) return;
  game.items.push(spawnItem(game.scene, spot));
  const taken = game.items.filter((i) => i.taken);
  // Recycle taken spots so the level never runs dry.
  if (taken.length > 6) game.spareSpots.push(taken.shift().cell);
}

function updateObjective() {
  const o = $('objective');
  if (game.def.endless) {
    o.textContent = `NIGHT SHIFT  ·  PARTS ${game.parts}  ·  ${store.fmtTime(game.time)}`;
  } else if (!game.hasKey) {
    o.textContent = `RADIO PARTS  ${game.parts}/${partsNeeded()}   ·   FIND THE KEY`;
  } else if (game.parts < partsNeeded()) {
    o.textContent = `RADIO PARTS  ${game.parts}/${partsNeeded()}`;
  } else {
    o.textContent = 'REACH THE SEWER HATCH';
  }
}

let msgTimer = 0;
function flash(text, secs = 2.5) {
  const m = $('message');
  m.textContent = text;
  m.style.opacity = 1;
  msgTimer = secs;
}

let hintTimer = 0;
function hint(text, secs = 5) {
  const h = $('hint');
  h.textContent = text;
  h.style.opacity = 1;
  hintTimer = secs;
}

// First-level hints, each shown once when its moment comes.
function tutorialHints() {
  return [
    { when: (g) => g.time > 1, text: 'WASD to move · mouse to look' },
    { when: (g) => g.time > 7, text: 'Hold C to crouch: silent, and low crates hide you' },
    { when: (g) => g.enforcers.some((e) => e.detection > 0.15), text: 'Stay out of their light. The eye at the top shows how close you are to being seen.' },
    { when: () => !game.player.hidden && nearbyLocker(), text: 'Press E to hide in the locker. Break line of sight first, or they will check it.' },
    { when: (g) => g.parts > 0, text: 'Every radio part brings another patrol. Move on quickly.' },
    { when: (g) => g.time > 20 && !g.player.flashOn, text: 'F for your flashlight. It helps you see, and helps them see you.' },
  ];
}

// ---- Checkpoints -----------------------------------------------------------

function saveCheckpoint() {
  game.checkpoint = {
    pos: game.player.pos.clone(),
    yaw: game.player.yaw,
    parts: game.parts,
    taken: game.items.map((i) => i.taken),
    hasKey: game.hasKey,
    difficulty: game.difficulty,
    enforcers: game.enforcers.length,
    time: game.time,
    spotted: game.spotted,
  };
}

function restoreCheckpoint() {
  const c = game.checkpoint;
  if (!c) return false;
  const def = game.def;
  const takenCells = game.items.filter((_, i) => c.taken[i]).map((i) => i.cell);
  const liveCells = game.items.filter((_, i) => !c.taken[i]).map((i) => i.cell);
  newRun(def);
  // Same part layout as the run we're continuing.
  game.items.forEach((i) => game.scene.remove(i.group));
  game.items = spawnItems(game.scene, liveCells);
  game.items.push(...takenCells.map((cell) => ({ group: new THREE.Group(), cell, taken: true })));
  game.parts = c.parts;
  game.difficulty = c.difficulty;
  game.time = c.time;
  game.spotted = c.spotted;
  if (c.hasKey && !game.hasKey) grantKey(true);
  game.player.pos.copy(c.pos);
  game.player.yaw = c.yaw;
  game.player.applyCamera(0);
  // Patrol count as it was, but everyone starts far from you.
  game.enforcers.forEach((e) => e.remove(game.scene, game.world));
  game.enforcers = [];
  for (let i = 0; i < c.enforcers; i++) {
    const far = farOpenCell(10);
    if (far) game.enforcers.push(new Enforcer(game.scene, game.level, far, game.difficulty));
  }
  game.checkpoint = c;
  if (game.parts >= partsNeeded()) game.world.hatch?.ringMat.color.setHex(0x22cc55);
  updateObjective();
  return true;
}

function grantKey(silent = false) {
  game.hasKey = true;
  unlockDoors(game.level);
  game.world.openDoors();
  game.enforcers.forEach((e) => e.refreshOpenCells());
  if (!silent) {
    sound.door();
    flash('Key found. The sealed doors are opening.', 3.5);
  }
  updateObjective();
}

// ---- Screens & input -------------------------------------------------------

function show(id) {
  ['menu', 'pause', 'end', 'settings'].forEach((s) => $(s).classList.toggle('hidden', s !== id));
  $('hud').classList.toggle('hidden', id !== null);
}

function lockPointer() {
  if (NO_LOCK) return;
  try {
    const p = renderer.domElement.requestPointerLock();
    p?.catch?.(() => {});
  } catch { /* browsers may refuse; clicking the canvas retries */ }
}

function startPlaying() {
  sound.start();
  sound.setVolume(settings.volume);
  game.state = 'playing';
  show(null);
  lockPointer();
  sdk.gameplayStart();
  last = performance.now();
}

function beginLevel(def) {
  newRun(def);
  flash(def.intro, 6);
  startPlaying();
}

function pause() {
  if (game.state !== 'playing') return;
  game.state = 'paused';
  show('pause');
  sound.suspend();
  sdk.gameplayStop();
}

function toMenu() {
  game.state = 'menu';
  sound.suspend();
  sdk.gameplayStop();
  if (document.pointerLockElement) document.exitPointerLock();
  renderMenu();
  show('menu');
}

function endRun(won, detail) {
  game.state = 'ended';
  sdk.gameplayStop();
  if (document.pointerLockElement) document.exitPointerLock();
  const t = $('end-title');
  const def = game.def;
  let text;
  if (won) {
    t.textContent = 'ESCAPED';
    t.className = 'win';
    text = `You slipped into the sewers with the radio parts in ${store.fmtTime(game.time)}. Spotted ${game.spotted} time${game.spotted === 1 ? '' : 's'}.`;
    if (store.recordEscape(def.id, game.levelIndex, game.time)) text += '<br><b>New best time!</b>';
    sdk.happytime();
    sdk.reportProgress(campaignProgress());
    if (def.tutorial) store.save({ seenTutorial: true });
  } else {
    t.textContent = 'DETAINED';
    t.className = 'lose';
    text = detail;
    if (def.endless) {
      text = `You lasted ${store.fmtTime(game.time)} and found ${game.parts} part${game.parts === 1 ? '' : 's'}.`;
      if (store.recordNight(game.parts, game.time)) text += '<br><b>New Night Shift record!</b>';
    }
  }
  $('end-text').innerHTML = text;
  const next = won && !def.endless && game.levelIndex < LEVELS.length - 1;
  $('next').classList.toggle('hidden', !next);
  $('continue').classList.toggle('hidden', won || !game.checkpoint);
  $('again').textContent = won ? 'Play again' : 'Restart level';
  setTimeout(() => show('end'), won ? 300 : 900);
}

// Menu: level list with best times and locks.
function renderMenu() {
  const s = store.load();
  const list = $('levels');
  list.innerHTML = '';
  LEVELS.forEach((def, i) => {
    const locked = i >= s.unlocked;
    const b = document.createElement('button');
    b.className = 'level' + (locked ? ' locked' : '');
    b.disabled = locked;
    const best = s.best[def.id];
    b.innerHTML = `<span class="n">${i + 1}</span><span class="name">${def.name}</span><span class="best">${locked ? 'LOCKED' : best ? store.fmtTime(best) : '—'}</span>`;
    b.onclick = () => beginLevel(def);
    list.appendChild(b);
  });
  const night = $('night');
  night.disabled = s.unlocked < 3;
  night.querySelector('.best').textContent = s.unlocked < 3 ? 'Escape level 2 to unlock' : s.nightBest ? `Record: ${s.nightBest} parts · ${store.fmtTime(s.nightBestTime)}` : 'Survive as long as you can';
  const cont = Math.min(s.unlocked, LEVELS.length) - 1;
  $('play').textContent = s.unlocked > 1 ? `Continue · ${LEVELS[cont].name}` : 'Play';
}

$('play').onclick = () => beginLevel(LEVELS[Math.min(store.load().unlocked, LEVELS.length) - 1]);
$('night').onclick = () => beginLevel(NIGHT_SHIFT);
$('resume').onclick = () => startPlaying();
$('restart-p').onclick = () => beginLevel(game.def);
$('menu-p').onclick = () => toMenu();
$('menu-e').onclick = () => toMenu();
$('next').onclick = () => beginLevel(LEVELS[game.levelIndex + 1]);
$('again').onclick = async () => {
  await sdk.midgameAd(() => sound.suspend(), () => sound.start());
  beginLevel(game.def);
};
$('continue').onclick = async () => {
  const ok = sdk.isReady() ? await sdk.rewardedAd(() => sound.suspend(), () => sound.start()) : true;
  if (!ok) { flash('Ad not available. Restart the level instead.', 3); return; }
  if (!restoreCheckpoint()) return;
  flash('Back at your last radio part. Patrols have moved.', 3.5);
  startPlaying();
};

// Settings.
const sens = $('sens');
const vol = $('vol');
const inv = $('invert');
function openSettings(from) {
  sens.value = settings.sensitivity;
  vol.value = settings.volume;
  inv.checked = settings.invertY;
  $('settings').dataset.from = from;
  show('settings');
}
function closeSettings() {
  settings.sensitivity = Number(sens.value);
  settings.volume = Number(vol.value);
  settings.invertY = inv.checked;
  store.save({ settings });
  sound.setVolume(settings.volume);
  show($('settings').dataset.from);
}
$('settings-m').onclick = () => openSettings('menu');
$('settings-p').onclick = () => openSettings('pause');
$('settings-back').onclick = () => closeSettings();
vol.oninput = () => sound.setVolume(Number(vol.value));

renderer.domElement.addEventListener('click', () => {
  if (game.state === 'playing' && !document.pointerLockElement) lockPointer();
});
// iOS/Safari suspend audio on interruptions; a gesture is needed to resume it.
['click', 'touchend', 'keydown'].forEach((ev) => document.addEventListener(ev, () => { if (game.state === 'playing') sound.start(); }));

document.addEventListener('pointerlockchange', () => {
  const locked = document.pointerLockElement === renderer.domElement;
  if (!locked && game.locked && game.state === 'playing') pause();
  game.locked = locked;
});

document.addEventListener('mousemove', (e) => {
  if (game.state !== 'playing') return;
  if (!document.pointerLockElement && !NO_LOCK) return;
  game.player.look(e.movementX, (settings.invertY ? -1 : 1) * e.movementY, 0.0022 * settings.sensitivity);
});

window.addEventListener('keydown', (e) => {
  if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.code)) e.preventDefault();
  if (e.code === 'KeyM') sound.setMuted(!sound.muted);
  if (game.state === 'paused' && e.code === 'Escape') return startPlaying();
  if (game.state !== 'playing') return;
  if (e.code === 'Escape' && NO_LOCK) return pause();
  game.player.keys.add(e.code);
  if (e.code === 'KeyE' && !e.repeat) interact();
  if (e.code === 'KeyF' && !e.repeat && !game.player.hidden) game.player.setFlashlight(!game.player.flashOn);
});
window.addEventListener('keyup', (e) => game.player?.keys.delete(e.code));
window.addEventListener('blur', () => { game.player?.keys.clear(); pause(); });

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// ---- Interaction -----------------------------------------------------------

function nearbyLocker() {
  const p = game.player;
  const f = p.forward();
  let best = null;
  let bestD = 1.6;
  for (const l of game.world.lockers) {
    const d = Math.hypot(l.exit.x - p.pos.x, l.exit.z - p.pos.z);
    const toL = new THREE.Vector3(l.pos.x - p.pos.x, 0, l.pos.z - p.pos.z).normalize();
    if (d < bestD && toL.dot(f) > 0.35) {
      best = l;
      bestD = d;
    }
  }
  return best;
}

function interact() {
  const p = game.player;
  if (p.hidden) {
    p.exitLocker();
    sound.locker();
    $('locker-view').classList.add('hidden');
    return;
  }
  const l = nearbyLocker();
  if (l) {
    p.setFlashlight(false);
    p.enterLocker(l);
    sound.locker();
    $('locker-view').classList.remove('hidden');
    // Close-by enforcers hear the locker door.
    game.enforcers.forEach((e) => e.hear(p.pos.clone(), 3.5, ctx));
  }
}

// ---- Main loop -------------------------------------------------------------

const ctx = {
  get player() { return game.player; },
  get world() { return game.world; },
  sound,
  listener: { pos: new THREE.Vector3(), yaw: 0 },
  onCaught(enforcer, fromLocker) {
    if (game.state !== 'playing') return;
    sound.caught();
    $('locker-view').classList.add('hidden');
    game.player.hidden = null;
    endRun(false, fromLocker
      ? 'They saw you climb into that locker. Next time, break line of sight before you hide.'
      : 'An Order patrol caught you after curfew. Stay low, stay dark, and keep the walls between you and their lights.');
  },
  onAlarm(cam) {
    sound.alarm();
    flash('CAMERA ALARM. Patrols are coming to you.', 3);
    const here = game.player.pos.clone();
    game.enforcers.forEach((e) => e.hear(here, 80, ctx, true));
  },
};

let last = performance.now();
function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  const t = now / 1000;

  if (game.world) {
    game.world.update(dt, game.player.pos);
    for (const it of game.items) {
      if (it.taken) continue;
      it.group.rotation.y += dt * 1.2;
      it.group.position.y = 0.8 + Math.sin(t * 2 + it.cell.x) * 0.08;
    }
    for (const k of game.keys) {
      if (k.taken) continue;
      k.group.rotation.y += dt * 1.5;
      k.group.position.y = 0.9 + Math.sin(t * 2.3) * 0.06;
    }
  }

  if (game.state === 'playing') update(dt, t);
  if (game.scene) renderer.render(game.scene, camera);
}

function update(dt, t) {
  const p = game.player;
  game.time += dt;
  if (game.def.endless && Math.floor(game.time) !== Math.floor(game.time - dt)) updateObjective();

  const noise = p.update(dt);
  if (noise) sound.footstep(p.crouched);
  if (noise > 0) game.enforcers.forEach((e) => e.hear(p.pos.clone(), noise, ctx));

  ctx.listener.pos.copy(p.pos);
  ctx.listener.yaw = p.yaw;

  let maxDet = 0;
  let chasing = false;
  for (const e of game.enforcers) {
    const was = e.state;
    e.update(dt, ctx);
    if (game.state !== 'playing') return;
    if (e.state === 'chase' && was !== 'chase') game.spotted++;
    maxDet = Math.max(maxDet, e.detection);
    chasing ||= e.state === 'chase' || e.state === 'check';
  }
  for (const c of game.cameras) {
    c.update(dt, t, ctx);
    maxDet = Math.max(maxDet, c.detection * 0.8);
  }

  if (!p.hidden) {
    // Pick up radio parts.
    for (const it of game.items) {
      if (it.taken) continue;
      if (Math.hypot(it.group.position.x - p.pos.x, it.group.position.z - p.pos.z) < 1.2) {
        it.taken = true;
        game.scene.remove(it.group);
        game.parts++;
        sound.pickup();
        game.difficulty += 0.07;
        game.enforcers.forEach((e) => (e.difficulty = game.difficulty));
        for (let i = 0; i < game.def.reinforce; i++) spawnReinforcement();
        if (game.def.endless) {
          spawnNextPart();
          flash(`Part ${game.parts}. Another patrol is on the floor.`);
        } else if (game.parts >= partsNeeded()) {
          flash(game.hasKey ? 'All parts found. Get to the sewer hatch.' : 'All parts found. Now the key.', 3.5);
          game.world.hatch.ringMat.color.setHex(0x22cc55);
        } else {
          flash(`Radio part ${game.parts}/${partsNeeded()}. More patrols are coming.`);
        }
        updateObjective();
        saveCheckpoint();
      }
    }
    // The key.
    for (const k of game.keys) {
      if (k.taken) continue;
      if (Math.hypot(k.group.position.x - p.pos.x, k.group.position.z - p.pos.z) < 1.2) {
        k.taken = true;
        game.scene.remove(k.group);
        sound.pickup();
        grantKey();
        saveCheckpoint();
      }
    }
  }

  // Escape.
  if (!game.def.endless && game.parts >= partsNeeded() && game.hasKey && !p.hidden) {
    const h = game.world.hatch.pos;
    if (Math.hypot(h.x - p.pos.x, h.z - p.pos.z) < 1.2) {
      sound.win();
      endRun(true);
      return;
    }
  }

  if (t > game.sirenAt) {
    sound.distantSiren();
    game.sirenAt = t + 45 + Math.random() * 45;
  }
  sound.updateHeart(chasing ? 1 : maxDet, t);

  // HUD.
  const fill = $('eye-fill');
  fill.style.width = `${Math.round((chasing ? 1 : maxDet) * 100)}%`;
  fill.style.background = chasing ? '#d42020' : maxDet > 0.4 ? '#e08a00' : '#c9b300';
  $('danger').style.opacity = chasing ? 0.55 + Math.sin(t * 8) * 0.15 : maxDet * 0.35;
  $('stamina-fill').style.width = `${p.stamina * 100}%`;
  $('stamina-fill').style.background = p.exhausted ? '#a33' : '#c9c3b0';
  $('status').textContent = [
    p.hidden ? 'HIDDEN' : p.crouched ? 'CROUCHING' : p.sprinting ? 'SPRINTING' : '',
    p.flashOn ? 'FLASHLIGHT ON' : '',
    game.hasKey && game.level.spawns.doors.length ? 'KEY' : '',
  ].filter(Boolean).join(' · ');
  const near = !p.hidden && nearbyLocker();
  $('prompt').textContent = p.hidden ? '[E] Leave locker' : near ? '[E] Hide in locker' : '';

  if (msgTimer > 0) {
    msgTimer -= dt;
    if (msgTimer <= 0) $('message').style.opacity = 0;
  }
  if (hintTimer > 0) {
    hintTimer -= dt;
    if (hintTimer <= 0) $('hint').style.opacity = 0;
  } else if (game.hints?.length) {
    const i = game.hints.findIndex((h) => h.when(game));
    if (i >= 0) {
      hint(game.hints[i].text);
      game.hints.splice(i, 1);
    }
  }
}

// Test hooks: advance the simulation without waiting on real frames, start a level by id.
game.simulate = (secs, dt = 1 / 30) => {
  const t0 = performance.now() / 1000;
  for (let i = 0; i * dt < secs && game.state === 'playing'; i++) update(dt, t0 + i * dt);
};
game.startLevel = (id) => beginLevel(byId(id));
game.restoreCheckpoint = restoreCheckpoint;

// ---- Boot ------------------------------------------------------------------

async function boot() {
  await sdk.initSDK();
  sdk.onSettings((s) => { if (s.muteAudio !== undefined) sound.setMuted(!!s.muteAudio); });
  const startId = params.get('level');
  newRun(startId ? byId(startId) : LEVELS[Math.min(store.load().unlocked, LEVELS.length) - 1]);
  renderMenu();
  requestAnimationFrame(frame);
  sdk.loadingDone();
  $('loading').classList.add('hidden');
  show('menu');
  // Park the menu camera somewhere moody.
  game.player.yaw = Math.PI * 0.75;
  game.player.applyCamera(0);
}
boot();
