// Thin wrapper around the CrazyGames SDK (v3). Every call is a no-op when the
// SDK is absent, so the game runs the same locally and on other portals.
// To enable on CrazyGames, add to index.html <head>:
//   <script src="https://sdk.crazygames.com/crazygames-sdk-v3.js"></script>
const sdk = () => window.CrazyGames?.SDK;
let ready = false;

export async function initSDK() {
  try {
    if (sdk()) {
      await sdk().init();
      ready = true;
    }
  } catch (e) {
    console.warn('CrazyGames SDK init failed', e);
  }
}

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

// Midgame ad between runs. Always resolves, ad or not.
export function midgameAd(onPause, onResume) {
  return new Promise((resolve) => {
    if (!ready) return resolve();
    try {
      sdk().ad.requestAd('midgame', {
        adStarted: () => onPause?.(),
        adFinished: () => { onResume?.(); resolve(); },
        adError: () => { onResume?.(); resolve(); },
      });
    } catch {
      resolve();
    }
  });
}
