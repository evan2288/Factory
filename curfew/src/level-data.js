// Parsing and queries for level maps. See levels.js for the map legend.
import { LEVELS } from './levels.js';

export const CELL = 2;
export const WALL_HEIGHT = 3.2;
export const MAP = LEVELS[1].map; // kept for older tooling
export const CAMERA_DIRS = { '^': [0, -1], v: [0, 1], '<': [-1, 0], '>': [1, 0] };

export const SOLID = new Set(['#', 'L', 'C', 'D']);

export function parseLevel(map = MAP) {
  const h = map.length;
  const w = map[0].length;
  const cells = [];
  const spawns = { player: null, enforcers: [], items: [], lights: [], lockers: [], crates: [], cameras: [], doors: [], keys: [], exit: null };
  for (let z = 0; z < h; z++) {
    const row = [];
    for (let x = 0; x < w; x++) {
      const ch = map[z][x];
      const p = { x, z };
      if (ch === 'P') spawns.player = p;
      else if (ch === 'E') spawns.enforcers.push(p);
      else if (ch === 'K') spawns.items.push(p);
      else if (ch === 'l') spawns.lights.push(p);
      else if (ch === 'L') spawns.lockers.push(p);
      else if (ch === 'C') spawns.crates.push(p);
      else if (ch === 'D') spawns.doors.push(p);
      else if (ch === 'k') spawns.keys.push(p);
      else if (ch === 'X') spawns.exit = p;
      else if (CAMERA_DIRS[ch]) spawns.cameras.push({ ...p, dir: CAMERA_DIRS[ch] });
      // Cameras, keys and spawn markers all stand on plain floor.
      row.push(SOLID.has(ch) || ch === '+' ? ch : '.');
    }
    cells.push(row);
  }
  return { w, h, cells, spawns };
}

export function isSolid(level, x, z) {
  if (x < 0 || z < 0 || x >= level.w || z >= level.h) return true;
  return SOLID.has(level.cells[z][x]);
}

// Cells that block sight. Crates only block sight to a crouched target.
export function blocksSight(level, x, z, targetCrouched) {
  if (x < 0 || z < 0 || x >= level.w || z >= level.h) return true;
  const ch = level.cells[z][x];
  if (ch === '#' || ch === 'L' || ch === 'D') return true;
  return ch === 'C' && targetCrouched;
}

// Opening the doors turns them into doorways for pathing and sight.
export function unlockDoors(level) {
  for (const d of level.spawns.doors) level.cells[d.z][d.x] = '+';
}

export const toWorld = (c) => c * CELL + CELL / 2;
export const toCell = (w) => Math.floor(w / CELL);
