import { storageGet, storageSet } from './sdk.js';

const KEY = 'curfew-save-v1';

const DEFAULTS = {
  unlocked: 1,              // how many campaign levels are playable
  best: {},                 // level id -> best escape time (seconds)
  nightBest: 0,             // Night Shift: most parts collected
  nightBestTime: 0,
  settings: { sensitivity: 1, volume: 0.8, invertY: false },
  seenTutorial: false,
};

let cache = null;

export function load() {
  if (cache) return cache;
  try {
    const raw = storageGet(KEY);
    cache = raw ? { ...DEFAULTS, ...JSON.parse(raw), settings: { ...DEFAULTS.settings, ...(JSON.parse(raw).settings || {}) } } : structuredClone(DEFAULTS);
  } catch {
    cache = structuredClone(DEFAULTS);
  }
  return cache;
}

export function save(patch = {}) {
  cache = { ...load(), ...patch };
  storageSet(KEY, JSON.stringify(cache));
  return cache;
}

export function recordEscape(levelId, levelIndex, time) {
  const s = load();
  const best = { ...s.best };
  const isBest = !best[levelId] || time < best[levelId];
  if (isBest) best[levelId] = time;
  save({ best, unlocked: Math.max(s.unlocked, levelIndex + 2) });
  return isBest;
}

export function recordNight(parts, time) {
  const s = load();
  const isBest = parts > s.nightBest || (parts === s.nightBest && time > s.nightBestTime);
  if (isBest) save({ nightBest: parts, nightBestTime: time });
  return isBest;
}

export const fmtTime = (secs) => `${Math.floor(secs / 60)}:${Math.floor(secs % 60).toString().padStart(2, '0')}`;
