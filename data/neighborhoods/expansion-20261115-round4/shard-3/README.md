# Round 4 shard 3 — 64 assigned names, 30 municipalities

The complete owned assignment is frozen in six independent batches. Read `summary.json` for the count, town breakdown and SHA256 of each `batch-*/features.geojson`. Import those six files once each; do not also scan technical maps or old expansion packets as new data.

All 64 names have one valid WGS84 Polygon/MultiPolygon candidate, explicitly estimated and low confidence, with no coordinate circle, point-only box, Voronoi cell or duplicate municipality/name. Some are full native named compounds; others are whole street/estate groups or broad agricultural-lane/field/forest estimates. These are practical search-area candidates, not certified official boundaries. Parent/child names and overlapping alternate divisions remain distinct. The maps show actual archived source geometry; their viewport frames are not output geometry.

The complete offline construction is in `build.py`, frozen specifications, EPSG:23700 map registrations and the root-owned shared `../contexts/` inputs. Source URLs, target label evidence, raw context paths/hashes, manual vertices and limitations are retained per feature. No source polygon was silently treated as a single-building substitute for an entire district. Native small scrub/orchard/inner-park fragments were rejected when incomplete.

Rebuild/verify each selected batch, for example:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round4/shard-3/build.py batch-05
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round4/shard-3/verify.py batch-05
```

All six per-batch byte-identical offline rebuilds passed. A cross-batch inventory check confirmed all 64 assigned keys exactly once. Geometry validity and label coverage are technical checks, not geographic precision validation.

Important remaining precision/identity questions are in `unresolved.json`: Göd's distant second OVIT point, very coarse Mogyoróska identity/extent, cross-municipal Sarlósár names, and Csikós/Csíkos spelling. No name was withheld, but these caveats must not disappear. The coarsest agricultural outlines deliberately favor usable whole physical lane/plot units over point-radius fallbacks, following the user's accepted estimation strategy.

This packet does not write MySQL, change application code, mutate old frozen packets/global aliases, or publish Git commits. The root agent owns global reconciliation, testing and GitHub checkpoints. Shared source: © OpenStreetMap contributors, ODbL-1.0; archived snapshot 2026-11-12T21:23:05Z, PBF SHA256 `224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a`.
