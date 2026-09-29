// Thin wrapper around the CrazyGames SDK (v3). Every call is a no-op when the
// SDK is absent, so the game runs the same locally and on other portals.
// index.html loads https://sdk.crazygames.com/crazygames-sdk-v3.js
const sdk = () => window.CrazyGames?.SDK;
let ready = false;
let lastMidgame = 0;

export async function initSDK() {
  try {
    if (sdk()) {
      // Never let a portal hiccup hold the menu hostage.
      await Promise.race([sdk().init(), new Promise((_, rej) => setTimeout(() => rej(new Error('sdk init timeout')), 4000))]);
      ready = true;
      try { sdk().game.loadingStart(); } catch { /* optional */ }
    }
  } catch (e) {
    console.warn('CrazyGames SDK init failed', e);
  }
  return ready;
}

export const isReady = () => ready;

export function loadingDone() {
  if (!ready) return;
  try { sdk().game.loadingStop(); } catch { /* optional */ }
}

export function gameplayStart() {
  if (!ready) return;
  try { sdk().game.gameplayStart(); } catch { /* optional */ }
}

export function gameplayStop() {
  if (!ready) return;
  try { sdk().game.gameplayStop(); } catch { /* optional */ }
}

export function happytime() {
  if (!ready) return;
  try { sdk().game.happytime(); } catch { /* optional */ }
}

export function reportProgress(pct) {
  if (!ready) return;
  try { sdk().game.reportGameCompletedPercentage(Math.round(pct)); } catch { /* optional */ }
}

// The portal can force audio off (e.g. a mute toggle in its UI).
export function onSettings(cb) {
  if (!ready) return;
  try {
    cb(sdk().game.settings || {});
    sdk().game.addSettingsChangeListener?.((s) => cb(s));
  } catch { /* optional */ }
}

// Midgame ad between runs. Always resolves, ad or not. Rate-limited to the
// portal's 3-minute rule so we never trigger an adCooldown error.
export function midgameAd(onPause, onResume) {
  return new Promise((resolve) => {
    if (!ready || performance.now() - lastMidgame < 180000) return resolve(false);
    lastMidgame = performance.now();
    let shown = false;
    try {
      sdk().ad.requestAd('midgame', {
        adStarted: () => { shown = true; onPause?.(); },
        adFinished: () => { onResume?.(); resolve(shown); },
        adError: () => { onResume?.(); resolve(false); },
      });
    } catch {
      resolve(false);
    }
  });
}

// Rewarded ad. Resolves true only if the ad was watched to the end.
export function rewardedAd(onPause, onResume) {
  return new Promise((resolve) => {
    if (!ready) return resolve(false);
    try {
      sdk().ad.requestAd('rewarded', {
        adStarted: () => onPause?.(),
        adFinished: () => { onResume?.(); resolve(true); },
        adError: () => { onResume?.(); resolve(false); },
      });
    } catch {
      resolve(false);
    }
  });
}

// Persistent storage: the portal's data module (synced for logged-in users),
// with localStorage as the fallback everywhere else.
export function storageGet(key) {
  try {
    if (ready) return sdk().data.getItem(key);
  } catch { /* fall through */ }
  try { return localStorage.getItem(key); } catch { return null; }
}

export function storageSet(key, value) {
  try {
    if (ready) sdk().data.setItem(key, value);
  } catch { /* fall through */ }
  try { localStorage.setItem(key, value); } catch { /* storage unavailable */ }
}
