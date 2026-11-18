# Native national surface extension

Offline extraction from the already archived national OpenStreetMap PBF. This
extends earlier passes that skipped named residential surfaces and rejected
all source areas containing more than one quarter label.

`features.geojson` has one chosen source footprint per new municipality/name.
It excludes names and aliases already present in the frozen baseline recorded
in `baseline-keys.json`. Its method and confidence distinguish two cases:

- `source-own-name-features.geojson`: an actual mapped residential/allotment,
  housing-estate or industrial-park surface carries the selected name itself.
  Infrastructure, schools, playgrounds, shops and individual buildings are
  excluded rather than promoted to neighborhood names because their names
  happen to mention a housing estate or industrial park.
- `single-label-features.geojson` / `multi-label-features.geojson`: an actual
  residential/allotment surface contains one or several archived named-place
  points. These are approximate named search footprints. Several names can
  share one source surface, including broad built-up areas; they are **not**
  distinct traced quarter borders. The smallest qualifying native source
  surface is preferred. Source-own names take priority over point containment.

Every coordinate is copied unchanged from original native member-ring
assembly. No circle, buffer, Voronoi, hull, clipping, snapping or simplification
is generated. Source geometry is preserved once in `raw-source-areas.geojson`;
`raw-associations.json` retains every considered name-to-surface association.
The raw layers allow a later smaller or better municipal polygon to replace a
broad footprint without losing either source.

Each feature records source URL, native ID, source tags, version, timestamp,
PBF SHA-256, municipal-reference ID, association method and optional name-point
ID/coordinates. OpenStreetMap data is ODbL-1.0, © OpenStreetMap contributors.

Regenerate using the archived PBF with `extract.py` and run
`validate-and-split.py` with the workspace geodata Python environment. The
validation concerns geometry integrity, preserved coordinates, point
containment and canonical name uniqueness. It does not claim official,
complete or geographically exact neighborhood boundaries.
