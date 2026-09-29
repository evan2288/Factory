# Curfew — CrazyGames listing

## Title
Curfew

## Short description (under 100 characters)
First-person stealth hide-and-seek. Find the radio parts, dodge the patrols, reach the sewer hatch.

## Description
The Order took the city, and curfew fell at dusk. You were still outside.

Curfew is a first-person stealth game about being hunted, not about fighting back. Sneak through an abandoned apartment block, find the radio parts, and reach the sewer hatch before a patrol catches you. Every part you take brings another patrol onto the floor.

- Patrols see along their flashlight beams and hear your footsteps. Crouch to move silently, keep your own light off, and stay out of the lamps.
- Hide in lockers, but break line of sight first: if they watch you climb in, they will check it.
- Security cameras call every patrol on the floor when they spot you.
- Sealed doors need a key. Find it before you carry the parts for nothing.
- Five levels of rising difficulty, plus Night Shift: an endless mode where the parts never stop and neither do the patrols.

No jump scares. The tension comes from the beam sweeping toward you and the heartbeat getting faster.

## Controls
- WASD / arrows: move
- Mouse: look (click to capture the mouse)
- Shift: sprint (fast but loud, uses stamina)
- C (hold): crouch (silent; low crates hide you)
- E: hide in / leave a locker
- F: flashlight (helps you see, helps them see you)
- Esc: pause · M: mute

## Category and tags
Category: Action → Stealth / Horror (no gore)
Tags: stealth, horror, first-person, 3D, hide and seek, escape, survival, single player, keyboard, mouse, WebGL

## Age rating notes
No blood, gore, violence shown, language or sexual content. Being caught fades to a "Detained" screen. Suitable for PEGI 12.

## Platform
Desktop only (mouse look with pointer lock). Works in Chrome, Edge, Firefox and Safari. Chromebook-friendly: no texture or audio downloads, all assets are generated in code.

## SDK
HTML5 SDK v3: init on the loading screen, loadingStart/Stop, gameplayStart/Stop on every menu/pause, happytime on each escape, reportGameCompletedPercentage from campaign progress, midgame ads between runs (rate-limited to 3 minutes), rewarded ad for "continue from your last radio part", Data module for saves (localStorage fallback), portal mute respected via settings listener.

## Assets (in `assets-out/` after `node scripts/assets.mjs` and `python3 scripts/finish-assets.py`)
- cover-landscape-1920x1080.png
- cover-portrait-800x1200.png
- cover-square-800x800.png
- preview-landscape-1920x1080.mp4 (18 s, silent, cover as first frame)
- preview-portrait-1080x1620.mp4 (18 s, silent, cover as first frame)
