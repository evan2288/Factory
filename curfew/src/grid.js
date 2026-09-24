import { isSolid, blocksSight, toCell, CELL } from './level-data.js';

const DIRS = [
  [1, 0], [-1, 0], [0, 1], [0, -1],
  [1, 1], [1, -1], [-1, 1], [-1, -1],
];

// A* over the cell grid. Diagonals are allowed only when both adjacent
// orthogonal cells are open, so agents never clip wall corners.
export function findPath(level, sx, sz, tx, tz) {
  if (isSolid(level, tx, tz)) return null;
  const key = (x, z) => z * level.w + x;
  const open = [{ x: sx, z: sz, g: 0, f: 0 }];
  const came = new Map();
  const gScore = new Map([[key(sx, sz), 0]]);
  const closed = new Set();
  const heur = (x, z) => Math.hypot(tx - x, tz - z);

  while (open.length) {
    let bi = 0;
    for (let i = 1; i < open.length; i++) if (open[i].f < open[bi].f) bi = i;
    const cur = open.splice(bi, 1)[0];
    const ck = key(cur.x, cur.z);
    if (cur.x === tx && cur.z === tz) {
      const path = [{ x: tx, z: tz }];
      let k = ck;
      while (came.has(k)) {
        k = came.get(k);
        path.push({ x: k % level.w, z: Math.floor(k / level.w) });
      }
      return path.reverse();
    }
    if (closed.has(ck)) continue;
    closed.add(ck);
    for (const [dx, dz] of DIRS) {
      const nx = cur.x + dx;
      const nz = cur.z + dz;
      if (isSolid(level, nx, nz)) continue;
      if (dx && dz && (isSolid(level, cur.x + dx, cur.z) || isSolid(level, cur.x, cur.z + dz))) continue;
      const nk = key(nx, nz);
      if (closed.has(nk)) continue;
      const g = cur.g + (dx && dz ? Math.SQRT2 : 1);
      if (g < (gScore.get(nk) ?? Infinity)) {
        gScore.set(nk, g);
        came.set(nk, ck);
        open.push({ x: nx, z: nz, g, f: g + heur(nx, nz) });
      }
    }
  }
  return null;
}

// Grid ray march between two world positions (x/z plane).
export function hasLineOfSight(level, ax, az, bx, bz, targetCrouched = false) {
  const dist = Math.hypot(bx - ax, bz - az);
  const steps = Math.ceil(dist / (CELL * 0.2));
  const tcx = toCell(bx);
  const tcz = toCell(bz);
  for (let i = 1; i < steps; i++) {
    const t = i / steps;
    const cx = toCell(ax + (bx - ax) * t);
    const cz = toCell(az + (bz - az) * t);
    if (cx === tcx && cz === tcz) break;
    if (blocksSight(level, cx, cz, targetCrouched)) return false;
  }
  return true;
}

export function openCells(level) {
  const out = [];
  for (let z = 0; z < level.h; z++)
    for (let x = 0; x < level.w; x++)
      if (!isSolid(level, x, z)) out.push({ x, z });
  return out;
}
