// Level layout. One character = one 2m x 2m cell.
//   #  wall            .  floor           +  doorway (floor)
//   L  locker (hide)   C  low crate/debris (cover when crouched)
//   P  player spawn    E  enforcer spawn  X  extraction hatch
//   K  possible radio-part spot (3 are picked at random each run)
//   l  hanging light (floor)
export const CELL = 2;
export const WALL_HEIGHT = 3.2;

export const MAP = [
  '######################################',
  '#P.....#.....L#.......L#.....#.......#',
  '#......#......#........#..C..#...K...#',
  '#..L...+......+...l....+.....+.......#',
  '#......#..C...#........#.....#...l..L#',
  '###+####..l...####+#####..l..###+#####',
  '#......#......#..........C...#.......#',
  '#..l...###+####..E......C....+..C....#',
  '#.............+.......l......#....K..#',
  '#..C...###+####...C..........###+#####',
  '#......#......#..........#####.......#',
  '###+####..K...#....X.....+...+...l..L#',
  '#......#......#####+######...#.......#',
  '#.l..L.+..l...#.......L..#.l.###+#####',
  '#......#......#...l......#...#...E...#',
  '#..K...#..C..L#.......K..+...+.......#',
  '#....C.#......#..........#...#..C..K.#',
  '######################################',
];

export const SOLID = new Set(['#', 'L', 'C']);

export function parseLevel(map = MAP) {
  const h = map.length;
  const w = map[0].length;
  const cells = [];
  const spawns = { player: null, enforcers: [], items: [], lights: [], lockers: [], crates: [], exit: null };
  for (let z = 0; z < h; z++) {
    const row = [];
    for (let x = 0; x < w; x++) {
      const ch = map[z][x];
      row.push(ch);
      const p = { x, z };
      if (ch === 'P') spawns.player = p;
      else if (ch === 'E') spawns.enforcers.push(p);
      else if (ch === 'K') spawns.items.push(p);
      else if (ch === 'l') spawns.lights.push(p);
      else if (ch === 'L') spawns.lockers.push(p);
      else if (ch === 'C') spawns.crates.push(p);
      else if (ch === 'X') spawns.exit = p;
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
  if (ch === '#' || ch === 'L') return true;
  return ch === 'C' && targetCrouched;
}

export const toWorld = (c) => c * CELL + CELL / 2;
export const toCell = (w) => Math.floor(w / CELL);
