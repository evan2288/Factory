#!/usr/bin/env bash
# Download the Natural Earth vector data the engine needs (public domain).
set -euo pipefail
cd "$(dirname "$0")/../data"
BASE="https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson"
for f in ne_10m_admin_1_states_provinces ne_50m_admin_0_countries ne_50m_lakes; do
  [ -s "$f.geojson" ] || curl -sSL --max-time 600 -o "$f.geojson" "$BASE/$f.geojson"
  echo "$f.geojson: $(du -h "$f.geojson" | cut -f1)"
done
