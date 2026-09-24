import * as THREE from 'three';
import { parseLevel, toCell } from './level-data.js';
import { buildWorld, spawnItems } from './world.js';
import { Player } from './player.js';
import { Enforcer } from './enforcer.js';
import { Sound } from './audio.js';
import { openCells } from './grid.js';
import * as sdk from './sdk.js';

const PARTS_NEEDED = 3;
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
const level = parseLevel();

const game = {
  state: 'menu',
  scene: null,
  world: null,
  player: null,
  enforcers: [],
  items: [],
  parts: 0,
  difficulty: 1,
  time: 0,
  spotted: 0,
  sirenAt: 30,
  locked: false,
};
window.__curfew = game;

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

function newRun() {
  disposeScene(game.scene);
  const scene = new THREE.Scene();
  scene.add(camera);
  camera.clear();
  game.scene = scene;
  game.world = buildWorld(scene, level);
  game.player = new Player(camera, level);
  game.items = spawnItems(scene, shuffle([...level.spawns.items]).slice(0, PARTS_NEEDED));
  game.difficulty = 1;
  game.enforcers = level.spawns.enforcers.map((c) => new Enforcer(scene, level, c, game.difficulty));
  game.parts = 0;
  game.time = 0;
  game.spotted = 0;
  game.sirenAt = 25 + Math.random() * 30;
  game.world.lockers.forEach((l) => (l.compromised = false));
  $('danger').style.opacity = 0;
  $('eye-fill').style.width = '0%';
  $('locker-view').classList.add('hidden');
  $('message').style.opacity = 0;
  updateObjective();
  game.player.applyCamera(0);
}

// A reinforcement arrives each time you grab a part, as far from you as possible.
function spawnReinforcement() {
  const p = game.player.pos;
  const pc = { x: toCell(p.x), z: toCell(p.z) };
  const far = openCells(level)
    .filter((c) => Math.hypot(c.x - pc.x, c.z - pc.z) > 12)
    .sort(() => Math.random() - 0.5)[0];
  if (!far) return;
  game.enforcers.push(new Enforcer(game.scene, level, far, game.difficulty));
}

function updateObjective() {
  $('objective').textContent = game.parts < PARTS_NEEDED
    ? `RADIO PARTS  ${game.parts}/${PARTS_NEEDED}`
    : 'REACH THE SEWER HATCH';
}

let msgTimer = 0;
function flash(text, secs = 2.5) {
  const m = $('message');
  m.textContent = text;
  m.style.opacity = 1;
  msgTimer = secs;
}

// ---- Screens & input -------------------------------------------------------

function show(id) {
  ['menu', 'pause', 'end'].forEach((s) => $(s).classList.toggle('hidden', s !== id));
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
  game.state = 'playing';
  show(null);
  lockPointer();
  sdk.gameplayStart();
  last = performance.now();
}

function pause() {
  if (game.state !== 'playing') return;
  game.state = 'paused';
  show('pause');
  sound.suspend();
  sdk.gameplayStop();
}

function endRun(won, detail) {
  game.state = 'ended';
  sdk.gameplayStop();
  if (document.pointerLockElement) document.exitPointerLock();
  const t = $('end-title');
  t.textContent = won ? 'ESCAPED' : 'DETAINED';
  t.className = won ? 'win' : 'lose';
  const mins = Math.floor(game.time / 60);
  const secs = Math.floor(game.time % 60).toString().padStart(2, '0');
  let text = won
    ? `You slipped into the sewers with the radio parts in ${mins}:${secs}. Spotted ${game.spotted} time${game.spotted === 1 ? '' : 's'}.`
    : detail;
  if (won) {
    try {
      const best = Number(localStorage.getItem('curfew-best') || 0);
      if (!best || game.time < best) {
        localStorage.setItem('curfew-best', String(game.time));
        text += '<br><b>New best time!</b>';
      }
    } catch { /* storage unavailable */ }
  }
  $('end-text').innerHTML = text;
  setTimeout(() => show('end'), won ? 300 : 900);
  showBest();
}

function showBest() {
  try {
    const best = Number(localStorage.getItem('curfew-best') || 0);
    if (best) $('best').textContent = `Best escape: ${Math.floor(best / 60)}:${Math.floor(best % 60).toString().padStart(2, '0')}`;
  } catch { /* storage unavailable */ }
}

$('play').onclick = () => startPlaying();
$('resume').onclick = () => startPlaying();
$('restart-p').onclick = () => { newRun(); startPlaying(); };
$('again').onclick = async () => {
  await sdk.midgameAd(() => sound.suspend(), () => sound.start());
  newRun();
  startPlaying();
};

renderer.domElement.addEventListener('click', () => {
  if (game.state === 'playing' && !document.pointerLockElement) lockPointer();
});

document.addEventListener('pointerlockchange', () => {
  const locked = document.pointerLockElement === renderer.domElement;
  if (!locked && game.locked && game.state === 'playing') pause();
  game.locked = locked;
});

document.addEventListener('mousemove', (e) => {
  if (game.state !== 'playing') return;
  if (!document.pointerLockElement && !NO_LOCK) return;
  game.player.look(e.movementX, e.movementY, 0.0022);
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
  get lights() { return game.world.lights; },
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
};

let last = performance.now();
function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  const t = now / 1000;

  if (game.world) {
    for (const l of game.world.lights) {
      if (!l.flicker) continue;
      l.t -= dt;
      if (l.t <= 0) {
        const off = Math.random() < 0.35;
        l.light.intensity = off ? 0.2 : l.base * (0.7 + Math.random() * 0.3);
        l.bulb.material.color.setHex(off ? 0x333333 : 0xffd9a0);
        l.t = off ? 0.05 + Math.random() * 0.25 : 0.2 + Math.random() * 3;
      }
    }
    for (const it of game.items) {
      if (it.taken) continue;
      it.group.rotation.y += dt * 1.2;
      it.group.position.y = 0.8 + Math.sin(t * 2 + it.cell.x) * 0.08;
    }
  }

  if (game.state === 'playing') update(dt, t);
  if (game.scene) renderer.render(game.scene, camera);
}

function update(dt, t) {
  const p = game.player;
  game.time += dt;

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

  // Pick up radio parts.
  if (!p.hidden) {
    for (const it of game.items) {
      if (it.taken) continue;
      if (Math.hypot(it.group.position.x - p.pos.x, it.group.position.z - p.pos.z) < 1.2) {
        it.taken = true;
        game.scene.remove(it.group);
        game.parts++;
        sound.pickup();
        updateObjective();
        game.difficulty += 0.07;
        game.enforcers.forEach((e) => (e.difficulty = game.difficulty));
        spawnReinforcement();
        if (game.parts >= PARTS_NEEDED) {
          flash('All parts found. Get to the sewer hatch.', 3.5);
          game.world.hatch.ringMat.color.setHex(0x22cc55);
        } else {
          flash(`Radio part ${game.parts}/${PARTS_NEEDED}. More patrols are coming.`);
        }
      }
    }
  }

  // Escape.
  if (game.parts >= PARTS_NEEDED && !p.hidden) {
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
  ].filter(Boolean).join(' · ');
  const near = !p.hidden && nearbyLocker();
  $('prompt').textContent = p.hidden ? '[E] Leave locker' : near ? '[E] Hide in locker' : '';

  if (msgTimer > 0) {
    msgTimer -= dt;
    if (msgTimer <= 0) $('message').style.opacity = 0;
  }
}

// Test hook: advance the simulation by `secs` without waiting on real frames.
game.simulate = (secs, dt = 1 / 30) => {
  const t0 = performance.now() / 1000;
  for (let i = 0; i * dt < secs && game.state === 'playing'; i++) update(dt, t0 + i * dt);
};

// ---- Boot ------------------------------------------------------------------

newRun();
showBest();
requestAnimationFrame(frame);
sdk.initSDK().then(() => sdk.loadingDone());

// Park the menu camera somewhere moody.
game.player.yaw = Math.PI * 0.75;
game.player.applyCamera(0);
