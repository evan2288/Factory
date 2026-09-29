# Curfew

A first-person stealth hide-and-seek game for the browser. The Order has taken
the city and you're caught out after curfew in an abandoned apartment block.
Find the radio parts and reach the sewer hatch without being detained.

Five levels (Ground Floor, The Block, Under Watch, Lockdown, The Tower) plus an
endless Night Shift mode. Later levels add security cameras that call every
patrol when they see you, and sealed doors that need a key.

No jump scares: the tension comes from being hunted.

## Play locally

```bash
cd curfew
npm install
npm run dev        # open the printed http://localhost:5173 link
```

## Controls

| Key | Action |
| --- | --- |
| WASD / arrows | Move |
| Mouse | Look (click the game to capture the mouse) |
| Shift | Sprint: fast but loud, uses stamina |
| C (hold) | Crouch: silent, and crates hide you |
| E | Hide in / leave a locker |
| F | Flashlight: helps you see, helps them see you |
| M | Mute |
| Esc | Pause |

## How the patrols work

- They see along their flashlight beam, and close up in their peripheral vision.
- You're harder to spot when crouched, standing still, in the dark, and with
  your flashlight off. Standing under a hanging light makes you easy to see.
- Sprinting footsteps carry about 13m and walking about 5m; crouching is silent.
  Noise sends them to investigate.
- The eye at the top of the screen shows how close you are to being spotted.
  Yellow means they're uneasy, orange means they're investigating, and red
  means they're chasing you.
- Break line of sight during a chase and they'll search where they last saw
  you. If they watch you climb into a locker, they'll check it.
- Every radio part you grab brings in another patrol and makes them all a
  little faster.

## Project layout

- `src/levels.js`: every map as text, with per-level settings (edit to change levels)
- `src/level-data.js`: map parsing, solidity and sight queries
- `src/camera.js`: security cameras
- `src/save.js`: progress, best times and settings (portal Data module or localStorage)
- `src/enforcer.js`: patrol AI (vision, hearing, chase, search, locker checks)
- `src/player.js`: movement, crouch/sprint/stamina, lockers, flashlight
- `src/world.js`, `src/textures.js`: level geometry and procedural textures
- `src/audio.js`: all sound, generated in code (no audio files)
- `src/sdk.js`: CrazyGames SDK hooks (no-ops unless the SDK script is loaded)

## Checks

```bash
npm test                                         # every level is valid, reachable, and doors gate the exit
npm run build && node scripts/scenarios.mjs .    # 22 scripted checks in headless Chromium, with screenshots
```

## Shipping to CrazyGames

```bash
npm run build                          # self-contained dist/ (about 150 KB gzipped, no image or audio files)
npm run zip                            # curfew-crazygames.zip with index.html at the root
node scripts/assets.mjs assets-out     # cover screenshots and preview frames
python3 scripts/finish-assets.py assets-out   # titled covers + silent preview videos
```

Upload `curfew-crazygames.zip` in the developer portal, then the three covers and
two preview videos from `assets-out/`. Listing text is in `STORE.md`. The SDK
script tag is already in `index.html`; every SDK call is a no-op outside the portal.
