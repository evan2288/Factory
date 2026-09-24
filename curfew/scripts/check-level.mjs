// Sanity checks for the level layout: run with `npm test`.
import { MAP, parseLevel, isSolid } from '../src/level-data.js';
import { findPath } from '../src/grid.js';

let failed = 0;
const fail = (msg) => { console.error('FAIL', msg); failed++; };

const widths = new Set(MAP.map((r) => r.length));
if (widths.size !== 1) fail(`rows have different widths: ${[...widths]}`);

const level = parseLevel();
for (let x = 0; x < level.w; x++) {
  if (level.cells[0][x] !== '#' || level.cells[level.h - 1][x] !== '#') fail(`border open at column ${x}`);
}
for (let z = 0; z < level.h; z++) {
  if (level.cells[z][0] !== '#' || level.cells[z][level.w - 1] !== '#') fail(`border open at row ${z}`);
}

const { player, enforcers, items, lockers, exit } = level.spawns;
if (!player) fail('no player spawn');
if (!exit) fail('no exit');
if (items.length < 3) fail('need at least 3 radio-part spots');
if (!enforcers.length) fail('no enforcer spawns');

const reach = (t, label) => {
  if (!findPath(level, player.x, player.z, t.x, t.z)) fail(`${label} at ${t.x},${t.z} unreachable`);
};
[...items, exit, ...enforcers].forEach((t, i) => reach(t, `target#${i}`));

// Every locker needs an open neighbour to be entered from.
for (const l of lockers) {
  const open = [[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dz]) => !isSolid(level, l.x + dx, l.z + dz));
  if (!open) fail(`locker at ${l.x},${l.z} has no open side`);
}

console.log(`level ${level.w}x${level.h}: ${items.length} part spots, ${lockers.length} lockers, ${enforcers.length} enforcer spawns`);
if (failed) { console.error(`${failed} problem(s)`); process.exit(1); }
console.log('level OK');
