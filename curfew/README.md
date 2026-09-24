# Curfew

A first-person stealth hide-and-seek game for the browser. The Order has taken
the city and you're caught out after curfew in an abandoned apartment block.
Find 3 radio parts and reach the sewer hatch without being detained.

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

- `src/level-data.js`: the map as text (edit it to change the level)
- `src/enforcer.js`: patrol AI (vision, hearing, chase, search, locker checks)
- `src/player.js`: movement, crouch/sprint/stamina, lockers, flashlight
- `src/world.js`, `src/textures.js`: level geometry and procedural textures
- `src/audio.js`: all sound, generated in code (no audio files)
- `src/sdk.js`: CrazyGames SDK hooks (no-ops unless the SDK script is loaded)

## Checks

```bash
npm test                                         # level layout is valid and fully reachable
npm run build && node scripts/scenarios.mjs .    # plays scripted scenarios in headless Chromium
```

## Shipping to CrazyGames

`npm run build` produces a self-contained `dist/` folder (about 150 KB
gzipped, with no image or audio files) that can be zipped and uploaded. Before
submitting, add the SDK script tag noted in `src/sdk.js` and check the current
requirements in the CrazyGames developer docs.
