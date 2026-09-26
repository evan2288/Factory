# future-map

Renders a "world map of the future" video: a political map whose borders change
at dated events, with a year counter and captions. Built so the borders can never
glitch: nothing is generated per frame by AI, and no border is ever hand-drawn.

## How the borders stay clean

- The world is a fixed set of ~4,500 **tiles** (Natural Earth 10m provinces for
  every country). A map state is just a table of *which country owns which tile*.
- A country's shape is the union of its tiles, so every border in every frame is
  a real present-day international or provincial line. Adjacent countries share
  identical edges, so shared borders are a single crisp line.
- Frames are rendered deterministically with Cairo (vector, antialiased). Two
  keyframes that differ in one province are pixel-identical everywhere else.
- Changes are shown as a short cross-fade between two keyframes with a highlight
  pulse over the changed tiles, then the map holds still while the year counts up.

## Layout

```
data/                Natural Earth GeoJSON (fetched, not committed)
scripts/fetch_data.sh
engine/build_tiles.py   project + snap tiles -> cache/tiles_WxH.pkl
engine/world.py         tile ownership, unions, colours, labels
engine/render.py        Cairo map + HUD rendering
engine/timeline.py      scenario JSON -> keyframes
engine/make_video.py    keyframes -> MP4 / stills
engine/list_provinces.py  authoring helper: province & region names per country
timeline/*.json         scenarios
out/                    renders (not committed)
```

## Run

```bash
pip install -r engine/requirements.txt
scripts/fetch_data.sh
python engine/build_tiles.py                    # once per resolution
python engine/make_video.py timeline/test_scenario.json --stills --out out/test.mp4
```

Fonts: the engine uses Montserrat and Bebas Neue from `../video-variants/engine/fonts`
(copy them to `~/.fonts` and run `fc-cache -f`). It falls back to system fonts.

## Writing a scenario

See the docstring at the top of `engine/timeline.py`. Each event lists tile
transfers; tiles are picked by country, province or region name
(`python engine/list_provinces.py "Iraq" "Spain"` prints the names).
