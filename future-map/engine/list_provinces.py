"""Print the provinces/regions available for a country, for scenario authoring.

Usage: python list_provinces.py "Iraq" ["Syria" ...]
"""
import sys
from collections import defaultdict

from world import Atlas


def main():
    atlas = Atlas()
    for admin in sys.argv[1:]:
        ids = atlas.tiles_of_admin(admin)
        by_region = defaultdict(list)
        for tid in ids:
            t = atlas.tiles[tid]
            by_region[t["region"] or "-"].append(t)
        print(f"== {admin} ({len(ids)} tiles)")
        for region, ts in sorted(by_region.items()):
            names = ", ".join(sorted(f"{t['name']}" + (f" [{t['alt']}]" if t['alt'] and t['alt'] != t['name'] else "")
                                     for t in ts))
            print(f"  region {region!r}: {names}")


if __name__ == "__main__":
    main()
