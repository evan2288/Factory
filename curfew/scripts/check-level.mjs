// Sanity checks for every level layout: run with `npm test`.
import { ALL_LEVELS } from '../src/levels.js';
import { parseLevel, isSolid, unlockDoors } from '../src/level-data.js';
import { findPath } from '../src/grid.js';

let failed = 0;

for (const def of ALL_LEVELS) {
  const fail = (msg) => { console.error(`FAIL [${def.id}] ${msg}`); failed++; };
  const widths = new Set(def.map.map((r) => r.length));
  if (widths.size !== 1) fail(`rows have different widths: ${[...widths]}`);

  const level = parseLevel(def.map);
  for (let x = 0; x < level.w; x++) {
    if (level.cells[0][x] !== '#' || level.cells[level.h - 1][x] !== '#') fail(`border open at column ${x}`);
  }
  for (let z = 0; z < level.h; z++) {
    if (level.cells[z][0] !== '#' || level.cells[z][level.w - 1] !== '#') fail(`border open at row ${z}`);
  }

  const { player, enforcers, items, lockers, exit, doors, keys, cameras } = level.spawns;
  if (!player) fail('no player spawn');
  if (!exit && !def.endless) fail('no exit');
  const need = def.endless ? 4 : def.partsNeeded + 1;
  if (items.length < need) fail(`need at least ${need} radio-part spots, have ${items.length}`);
  if (!enforcers.length) fail('no enforcer spawns');
  if (doors.length && !keys.length) fail('doors but no key');

  const reach = (t, label) => {
    if (!findPath(level, player.x, player.z, t.x, t.z)) fail(`${label} at ${t.x},${t.z} unreachable`);
  };
  // Before the key: parts, patrol spawns and the key itself must be reachable; the exit must not be (if doors exist).
  items.forEach((t, i) => reach(t, `part spot #${i}`));
  enforcers.forEach((t, i) => reach(t, `enforcer spawn #${i}`));
  keys.forEach((t, i) => reach(t, `key #${i}`));
  if (exit && doors.length && findPath(level, player.x, player.z, exit.x, exit.z)) fail('exit reachable without the key');
  if (exit && !doors.length) reach(exit, 'exit');

  for (const c of cameras) {
    if (isSolid(level, c.x + c.dir[0], c.z + c.dir[1])) fail(`camera at ${c.x},${c.z} faces a wall`);
  }
  for (const l of lockers) {
    const open = [[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dz]) => !isSolid(level, l.x + dx, l.z + dz));
    if (!open) fail(`locker at ${l.x},${l.z} has no open side`);
  }

  if (doors.length) {
    unlockDoors(level);
    if (exit) reach(exit, 'exit (after unlocking)');
    for (const d of doors) {
      const sides = [[1, 0], [-1, 0], [0, 1], [0, -1]].filter(([dx, dz]) => !isSolid(level, d.x + dx, d.z + dz)).length;
      if (sides < 2) fail(`door at ${d.x},${d.z} does not connect two open cells`);
    }
  }

  console.log(`[${def.id}] ${level.w}x${level.h}: ${items.length} part spots, ${lockers.length} lockers, ${enforcers.length} patrols, ${cameras.length} cameras, ${doors.length} doors, ${level.spawns.lights.length} lights`);
}

if (failed) { console.error(`${failed} problem(s)`); process.exit(1); }
console.log('all levels OK');
