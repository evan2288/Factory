"""Timeline: a list of dated events, each a set of tile-ownership changes.

Scenario JSON shape:
{
  "title": "...", "start_year": 2025,
  "hold_seconds": 4.0, "transition_seconds": 1.2, "settle_seconds": 1.5,
  "events": [
    {"year": 2034, "title": "Kurdistan declares independence",
     "subtitle": "optional one-liner",
     "changes": [
       {"to": "KRD", "name": "Kurdistan", "color": "#c9736a",
        "take": [{"from": "Iraq", "provinces": ["Erbil", "Dahuk"]},
                 {"from": "Turkey", "regions": ["Southeast Anatolia"]},
                 {"country": "SOMEID"}]},            # every tile a live country holds now
       {"to": "SDN_RSF", "name": "RSF", "rebel": true,       # civil-war faction: hatched fill
        "take": [{"from": "Sudan", "regions": ["Darfur"]}]},
       {"rename": "RUS", "name": "Russian Federation"},
       {"recolor": "CHN", "color": "#..."}
     ]}
  ]
}
`from` selects present-day tiles by country/province/region name (see
list_provinces.py); `country` selects whatever a country owns at that moment.
"""
import json
from dataclasses import dataclass, field
from typing import List

from shapely import unary_union

from world import Atlas, World


@dataclass
class Keyframe:
    year: float
    title: str
    subtitle: str
    world: World
    changed: object            # shapely geometry of tiles whose owner changed
    hold: float
    transition: float
    settle: float
    changed_ids: List[str] = field(default_factory=list)


def _resolve_take(atlas: Atlas, world: World, item):
    if "country" in item:
        return world.tiles_of(item["country"])
    return atlas.select(item["from"], item.get("provinces"), item.get("regions"), item.get("exclude"))


def build(scenario_path, atlas: Atlas):
    sc = json.load(open(scenario_path))
    hold = sc.get("hold_seconds", 4.0)
    trans = sc.get("transition_seconds", 1.2)
    settle = sc.get("settle_seconds", 1.5)

    world = World.present_day(atlas, sc.get("group_dependencies", True))
    frames = [Keyframe(sc.get("start_year", 2025), sc.get("title", ""), sc.get("subtitle", ""),
                       world, None, sc.get("intro_seconds", 4.0), 0, 0)]

    for ev in sc["events"]:
        before = world
        moved = []
        for ch in ev.get("changes", []):
            if "rename" in ch:
                world = world.rename(ch["rename"], ch["name"])
            elif "recolor" in ch:
                world = world.recolor(ch["recolor"], ch["color"])
            else:
                tiles = []
                for item in ch["take"]:
                    tiles += _resolve_take(atlas, world, item)
                tiles = [t for t in tiles if world.owner[t] != ch["to"]]
                moved += tiles
                world = world.transfer(tiles, ch["to"], ch.get("name"), ch.get("color"),
                                       "rebel" if ch.get("rebel") else None)
        changed = unary_union([atlas.geom[t] for t in moved]) if moved else None
        frames.append(Keyframe(ev["year"], ev.get("title", ""), ev.get("subtitle", ""), world, changed,
                               ev.get("hold", hold), ev.get("transition", trans), ev.get("settle", settle),
                               moved))
        _ = before
    return sc, frames
