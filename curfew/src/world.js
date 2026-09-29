import * as THREE from 'three';
import { CELL, WALL_HEIGHT, isSolid, toWorld } from './level-data.js';
import * as tex from './textures.js';

// Only this many point lights are ever live: they're re-assigned every frame
// to the hanging lamps nearest the player. Keeps integrated GPUs happy on the
// large levels (every extra light costs every pixel).
const LIGHT_POOL = 6;
// Same idea for flashlight/camera beams: a few real spotlights follow the
// nearest patrols and cameras; the rest only draw their translucent cone.
const SPOT_POOL = 4;

// Builds all static geometry for a parsed level and returns handles to the
// animated/interactive bits (lights, lockers, doors, key, cameras, exit hatch).
export function buildWorld(scene, level) {
  const W = level.w * CELL;
  const H = level.h * CELL;

  scene.background = new THREE.Color(0x030405);
  scene.fog = new THREE.FogExp2(0x040506, 0.06);
  scene.add(new THREE.HemisphereLight(0x51667a, 0x14100c, 2.4));

  // Floor and ceiling.
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(W, H),
    new THREE.MeshStandardMaterial({ map: tex.floorTexture([level.w, level.h]), roughness: 0.92 }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(W / 2, 0, H / 2);
  scene.add(floor);

  const ceiling = new THREE.Mesh(
    new THREE.PlaneGeometry(W, H),
    new THREE.MeshStandardMaterial({ map: tex.ceilingTexture([level.w, level.h]), roughness: 1 }),
  );
  ceiling.rotation.x = Math.PI / 2;
  ceiling.position.set(W / 2, WALL_HEIGHT, H / 2);
  scene.add(ceiling);

  // Walls: one instanced box per wall cell that borders open space.
  const wallCells = [];
  for (let z = 0; z < level.h; z++) {
    for (let x = 0; x < level.w; x++) {
      if (level.cells[z][x] !== '#') continue;
      const exposed = [[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dz]) => {
        const c = level.cells[z + dz]?.[x + dx];
        return c && c !== '#';
      });
      if (exposed) wallCells.push({ x, z });
    }
  }
  const walls = new THREE.InstancedMesh(
    new THREE.BoxGeometry(CELL, WALL_HEIGHT, CELL),
    new THREE.MeshStandardMaterial({ map: tex.wallTexture(), roughness: 0.95 }),
    wallCells.length,
  );
  const m = new THREE.Matrix4();
  wallCells.forEach((c, i) => {
    m.makeTranslation(toWorld(c.x), WALL_HEIGHT / 2, toWorld(c.z));
    walls.setMatrixAt(i, m);
  });
  scene.add(walls);

  // Crates (low cover).
  const crateMat = new THREE.MeshStandardMaterial({ map: tex.crateTexture(), roughness: 0.9 });
  for (const c of level.spawns.crates) {
    const g = new THREE.Group();
    const big = new THREE.Mesh(new THREE.BoxGeometry(1.7, 1.1, 1.7), crateMat);
    big.position.y = 0.55;
    g.add(big);
    const small = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.5, 0.8), crateMat);
    small.position.set(0.35, 1.35, -0.3);
    small.rotation.y = 0.5;
    g.add(small);
    g.position.set(toWorld(c.x), 0, toWorld(c.z));
    g.rotation.y = ((c.x * 7 + c.z * 3) % 5) * 0.12;
    scene.add(g);
  }

  // Lockers / cabinets you can hide in. Each remembers which open side faces out.
  const lockerMat = new THREE.MeshStandardMaterial({ map: tex.lockerTexture(), roughness: 0.6, metalness: 0.4 });
  const lockers = level.spawns.lockers.map((c) => {
    const dirs = [[0, 1], [0, -1], [1, 0], [-1, 0]];
    const [fx, fz] = dirs.find(([dx, dz]) => !isSolid(level, c.x + dx, c.z + dz));
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(1.8, 2.4, 1.8), lockerMat);
    mesh.position.set(toWorld(c.x), 1.2, toWorld(c.z));
    mesh.rotation.y = Math.atan2(fx, fz);
    scene.add(mesh);
    return {
      cell: c,
      facing: { x: fx, z: fz },
      pos: new THREE.Vector3(toWorld(c.x), 0, toWorld(c.z)),
      exit: new THREE.Vector3(toWorld(c.x + fx), 0, toWorld(c.z + fz)),
      compromised: false,
    };
  });

  // Locked doors: steel shutters that slide up when the key is found.
  const doorMat = new THREE.MeshStandardMaterial({ map: tex.doorTexture(), roughness: 0.5, metalness: 0.6 });
  const doors = level.spawns.doors.map((c) => {
    const horizontal = !isSolid(level, c.x - 1, c.z) || !isSolid(level, c.x + 1, c.z);
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(horizontal ? 0.3 : CELL, WALL_HEIGHT, horizontal ? CELL : 0.3), doorMat);
    mesh.position.set(toWorld(c.x), WALL_HEIGHT / 2, toWorld(c.z));
    scene.add(mesh);
    const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.07, 8, 6), new THREE.MeshBasicMaterial({ color: 0xff2a1a }));
    lamp.position.set(toWorld(c.x), WALL_HEIGHT - 0.25, toWorld(c.z));
    scene.add(lamp);
    return { cell: c, mesh, lamp, open: 0 };
  });

  // The key.
  const keys = level.spawns.keys.map((c) => {
    const g = new THREE.Group();
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.12, 0.025, 8, 20), new THREE.MeshStandardMaterial({ color: 0xd8b452, metalness: 0.9, roughness: 0.3 }));
    g.add(ring);
    const blade = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.28, 0.03), new THREE.MeshStandardMaterial({ color: 0xd8b452, metalness: 0.9, roughness: 0.3 }));
    blade.position.y = -0.24;
    g.add(blade);
    const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture('rgba(255,220,120,0.9)'), blending: THREE.AdditiveBlending, depthWrite: false }));
    glow.scale.set(1.1, 1.1, 1);
    g.add(glow);
    g.position.set(toWorld(c.x), 0.9, toWorld(c.z));
    scene.add(g);
    return { group: g, cell: c, taken: false };
  });

  // Hanging lights: lamp fixtures everywhere, real point lights from a small pool.
  const bulbMat = new THREE.MeshBasicMaterial({ color: 0xffd9a0 });
  const cordMat = new THREE.MeshBasicMaterial({ color: 0x111111 });
  const lights = level.spawns.lights.map((c, i) => {
    const x = toWorld(c.x);
    const z = toWorld(c.z);
    const pos = new THREE.Vector3(x, WALL_HEIGHT - 0.7, z);
    const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.09, 8, 6), bulbMat.clone());
    bulb.position.copy(pos);
    scene.add(bulb);
    const cord = new THREE.Mesh(new THREE.CylinderGeometry(0.01, 0.01, 0.6), cordMat);
    cord.position.set(x, WALL_HEIGHT - 0.35, z);
    scene.add(cord);
    const base = 22;
    return { pos, bulb, base, intensity: base, flicker: i % 3 === 0, t: Math.random() * 10, light: null };
  });
  const pool = [];
  for (let i = 0; i < Math.min(LIGHT_POOL, lights.length); i++) {
    const light = new THREE.PointLight(0xffc98a, 0, 13, 1.5);
    scene.add(light);
    pool.push(light);
  }

  // Propaganda posters on random exposed wall faces.
  let seed = 3;
  let posters = 0;
  for (let z = 1; z < level.h - 1 && posters < 16; z++) {
    for (let x = 1; x < level.w - 1 && posters < 16; x++) {
      if (level.cells[z][x] !== '#') continue;
      seed = (seed * 31 + x * 17 + z * 13) % 101;
      if (seed > 12) continue;
      for (const [dx, dz] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
        const n = level.cells[z + dz]?.[x + dx];
        if (!n || isSolid(level, x + dx, z + dz)) continue;
        const p = new THREE.Mesh(
          new THREE.PlaneGeometry(0.8, 0.8),
          new THREE.MeshStandardMaterial({ map: tex.posterTexture(x * 100 + z), roughness: 1 }),
        );
        p.position.set(toWorld(x) + dx * (CELL / 2 + 0.01), 1.7, toWorld(z) + dz * (CELL / 2 + 0.01));
        p.rotation.y = Math.atan2(dx, dz);
        p.rotation.z = (seed % 7 - 3) * 0.03;
        scene.add(p);
        posters++;
        break;
      }
    }
  }

  // Extraction hatch.
  let hatch = null;
  const ex = level.spawns.exit;
  if (ex) {
    const group = new THREE.Group();
    const lid = new THREE.Mesh(
      new THREE.CylinderGeometry(0.7, 0.7, 0.06, 24),
      new THREE.MeshStandardMaterial({ color: 0x2b2d2e, metalness: 0.7, roughness: 0.5 }),
    );
    lid.position.y = 0.03;
    group.add(lid);
    const ringMat = new THREE.MeshBasicMaterial({ color: 0x661111 });
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.75, 0.05, 8, 32), ringMat);
    ring.rotation.x = Math.PI / 2;
    ring.position.y = 0.07;
    group.add(ring);
    group.position.set(toWorld(ex.x), 0, toWorld(ex.z));
    scene.add(group);
    hatch = { group, ringMat, pos: group.position };
  }

  const spots = [];
  for (let i = 0; i < SPOT_POOL; i++) {
    const sl = new THREE.SpotLight(0xffffff, 0, 20, 0.6, 0.45, 1.25);
    scene.add(sl);
    scene.add(sl.target);
    spots.push(sl);
  }

  // Beam sources (patrols, cameras) register here; see Enforcer/SecurityCamera.
  const world = { lights, pool, spots, beams: [], lockers, doors, keys, hatch, size: { W, H } };

  // Per-frame: flicker, assign the light pool to the nearest lamps, animate doors.
  world.update = (dt, playerPos) => {
    for (const l of lights) {
      if (!l.flicker) continue;
      l.t -= dt;
      if (l.t <= 0) {
        const off = Math.random() < 0.35;
        l.intensity = off ? 0.2 : l.base * (0.7 + Math.random() * 0.3);
        l.bulb.material.color.setHex(off ? 0x333333 : 0xffd9a0);
        l.t = off ? 0.05 + Math.random() * 0.25 : 0.2 + Math.random() * 3;
      }
    }
    if (pool.length) {
      const nearest = lights
        .map((l) => ({ l, d: l.pos.distanceToSquared(playerPos) }))
        .sort((a, b) => a.d - b.d)
        .slice(0, pool.length);
      lights.forEach((l) => (l.light = null));
      nearest.forEach(({ l }, i) => {
        pool[i].position.copy(l.pos);
        pool[i].intensity = l.intensity;
        l.light = pool[i];
      });
    }
    if (spots.length) {
      const live = world.beams
        .filter((b) => b.on)
        .map((b) => ({ b, d: b.pos.distanceToSquared(playerPos) }))
        .sort((a, c) => a.d - c.d)
        .slice(0, spots.length);
      spots.forEach((sl, i) => {
        const src = live[i]?.b;
        if (!src) { sl.intensity = 0; return; }
        sl.position.copy(src.pos);
        sl.target.position.copy(src.target);
        sl.color.setHex(src.color);
        sl.intensity = src.intensity;
        sl.angle = src.angle;
        sl.distance = src.distance;
        sl.penumbra = src.penumbra;
      });
    }
    for (const d of doors) {
      if (d.open < 1 && d.opening) {
        d.open = Math.min(1, d.open + dt * 0.6);
        d.mesh.position.y = WALL_HEIGHT / 2 + d.open * (WALL_HEIGHT - 0.25);
        if (d.open >= 1) d.mesh.visible = false;
      }
    }
  };

  world.openDoors = () => {
    for (const d of doors) {
      d.opening = true;
      d.lamp.material.color.setHex(0x22cc55);
    }
  };

  return world;
}

// Is this world position lit by a lamp that's currently bright?
export function isLit(world, pos) {
  return world.lights.some((l) => l.intensity > 1 && l.pos.distanceTo(pos) < 4.5);
}

function glowTexture(color) {
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const g = c.getContext('2d');
  const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grd.addColorStop(0, color);
  grd.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = grd;
  g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

// Radio parts: glowing, bobbing pickups.
export function spawnItems(scene, spots) {
  const glowTex = glowTexture('rgba(140,255,170,0.9)');
  return spots.map((c) => spawnItem(scene, c, glowTex));
}

export function spawnItem(scene, c, glowTex = glowTexture('rgba(140,255,170,0.9)')) {
  const g = new THREE.Group();
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(0.35, 0.2, 0.22),
    new THREE.MeshStandardMaterial({ color: 0x2c3a2e, emissive: 0x1d6b33, emissiveIntensity: 0.8, metalness: 0.5 }),
  );
  g.add(body);
  const ant = new THREE.Mesh(new THREE.CylinderGeometry(0.01, 0.01, 0.35), new THREE.MeshBasicMaterial({ color: 0x999999 }));
  ant.position.set(0.12, 0.25, 0);
  g.add(ant);
  const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, blending: THREE.AdditiveBlending, depthWrite: false }));
  glow.scale.set(1.3, 1.3, 1);
  g.add(glow);
  g.position.set(toWorld(c.x), 0.8, toWorld(c.z));
  scene.add(g);
  return { group: g, cell: c, taken: false };
}
