import * as THREE from 'three';
import { CELL, WALL_HEIGHT, isSolid, toWorld } from './level-data.js';
import * as tex from './textures.js';

// Builds all static geometry for a parsed level and returns handles to the
// animated/interactive bits (lights, radio parts, exit hatch).
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

  // Hanging lights. Some flicker.
  const bulbMat = new THREE.MeshBasicMaterial({ color: 0xffd9a0 });
  const cordMat = new THREE.MeshBasicMaterial({ color: 0x111111 });
  const lights = level.spawns.lights.map((c, i) => {
    const x = toWorld(c.x);
    const z = toWorld(c.z);
    const light = new THREE.PointLight(0xffc98a, 22, 13, 1.5);
    light.position.set(x, WALL_HEIGHT - 0.7, z);
    scene.add(light);
    const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.09, 8, 6), bulbMat.clone());
    bulb.position.copy(light.position);
    scene.add(bulb);
    const cord = new THREE.Mesh(new THREE.CylinderGeometry(0.01, 0.01, 0.6), cordMat);
    cord.position.set(x, WALL_HEIGHT - 0.35, z);
    scene.add(cord);
    return { light, bulb, base: light.intensity, flicker: i % 3 === 0, t: Math.random() * 10, pos: light.position };
  });

  // Propaganda posters on random exposed wall faces.
  const posters = [];
  let seed = 3;
  for (let z = 1; z < level.h - 1 && posters.length < 14; z++) {
    for (let x = 1; x < level.w - 1 && posters.length < 14; x++) {
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
        posters.push(p);
        break;
      }
    }
  }

  // Extraction hatch.
  const ex = level.spawns.exit;
  const hatch = new THREE.Group();
  const lid = new THREE.Mesh(
    new THREE.CylinderGeometry(0.7, 0.7, 0.06, 24),
    new THREE.MeshStandardMaterial({ color: 0x2b2d2e, metalness: 0.7, roughness: 0.5 }),
  );
  lid.position.y = 0.03;
  hatch.add(lid);
  const ringMat = new THREE.MeshBasicMaterial({ color: 0x661111 });
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.75, 0.05, 8, 32), ringMat);
  ring.rotation.x = Math.PI / 2;
  ring.position.y = 0.07;
  hatch.add(ring);
  hatch.position.set(toWorld(ex.x), 0, toWorld(ex.z));
  scene.add(hatch);

  return { lights, lockers, hatch: { group: hatch, ringMat, pos: hatch.position }, size: { W, H } };
}

// Radio parts: glowing, bobbing pickups.
export function spawnItems(scene, spots) {
  const glowTex = (() => {
    const c = document.createElement('canvas');
    c.width = c.height = 64;
    const g = c.getContext('2d');
    const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    grd.addColorStop(0, 'rgba(140,255,170,0.9)');
    grd.addColorStop(1, 'rgba(140,255,170,0)');
    g.fillStyle = grd;
    g.fillRect(0, 0, 64, 64);
    return new THREE.CanvasTexture(c);
  })();
  return spots.map((c) => {
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
  });
}
