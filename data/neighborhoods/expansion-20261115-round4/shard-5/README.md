# Eastern band, round 4, shard 5 — frozen

All **66 target names in 44 municipalities** have WGS84 Polygon/MultiPolygon search-area estimates. All 66 were attempted and all remain explicitly `estimated: true`, `lowConfidence: true`; zero circles, rectangles, Voronoi cells or deleted names were used. `features.geojson` is the complete intake file. SHA-256: `bd36bf6990cfb2cff4c1599b89d02d351b2c8c5ba863043db19569cb7dbc5cf1`.

Four immutable intake snapshots contain 20 + 20 + 20 + 6 features under `batches/`. Their concatenation matches `features.geojson`; `validation.json` records individual hashes. No old packet, registry, generated global file or Git state was edited.

The geometry uses 39 selected actual road/water/railway enclosures, seven mapped land-use/locality associations, 17 manually selected named-street or campus envelopes, one source-table remainder, one constituent union and one municipal-text/native-shoreline partition. Existing name points select and name source candidates; point coordinates never generate a distance-based shape. All street-envelope connections, local-name associations and historical quarter borders remain inferred. Internal blocks are included together for whole quarters, and dispersed localities include agricultural context where the surrounding real network supports it. Historical subdivisions may overlap.

Special source interpretations:

- **Pepi-kert:** operator, university and heritage usage supports associating the literal Szarvasi Arborétum footprint with the common modern name. The older approximately 40 ha Pepi garden is a historical subset whose exact limits were not established. The literal 80.7 ha park footprint crosses the cached Szarvas municipality geometry: 47.1% falls outside that source border. The full source park is retained; no administrative split is asserted.
- **Dembrovszky-tanya:** the compact mapped farmyard contains the name point. Its 2.1 ha footprint represents the farmstead, excluding outlying historical fields.
- **Miskolc:** the primary ITS table identifies the three names as distinct KSH units within larger planning groups. Martin kertvárosi felüljáró uses the whole approximately 20.2 ha rail-transport site at the Martin access, not a bridge footprint. Szondi–Csorbatelep uses the broad approximately 11.27 km² group-2 remainder after removing the archived coarse Selyemrét outline and Martin rail site; its internal partition is inferred, not published KSH geometry. Vologda–Jókai is the union of independently archived constituent estimates. The complete 17-unit parent group was not blindly assigned to each name.
- **Halászfalu:** Tokaj TAK gives Rév köz–Szepesy L.–Mosolygó I.–Zákó köz–Bodrogpart as bounds. A frontage-aware mask follows the corresponding mapped streets and intersects a literal native urban footprint for the coast. Differences in street spelling and frontage placement remain approximate.
- **Nyíradony-Gúthpuszta:** the forestry operator's table explicitly lists municipality Nyírmártonfalva with this Nyíradony postal address. The compact inhabited forestry locality is represented, excluding the entire approximately 5000 ha Gúthi forest.
- **Győrliget/Györgyliget and Kiserdő/Kisibrány:** no alias is assumed. Municipal legislation separately names Győrliget and Györgyliget. Kiserdő and Kisibrány have distinct, overlapping street-envelope estimates.

The name label lies 237 m outside the selected Felsőzsolcai Ipari Zóna street/campus envelope; development/reserve-land membership there is uncertain. Dózsatelep and Vajai Ipari park labels are respectively 22 m and 45 m outside their selected physical outlines. These source labels are approximate localization evidence, not surveyed boundary anchors. The features remain low confidence; `validation.json` preserves these checks rather than silently stretching geometry to a point.

Rebuild offline using the preserved input snapshots:

```
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round4/shard-5/build.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round4/shard-5/validate.py
```

`selection.json` is the authoritative manual decision record. `build.py` reconstructs selected enclosures from real source lines, builds the other source-based estimates, validates geometry and checks prior batch contents without changing them. The `append-batch*.py` and `initialize.py` scripts preserve collection-stage decisions; they are not the final rebuild entry point. Refinements are retained in authoritative selection records.

`source-inputs/` holds compressed offline OSM contexts, literal Tokaj urban geometry, Miskolc constituent/parent outlines, exact primary source text and the explicitly estimated Tokaj mask. `provenance.json` records OSM extraction hashes and source metadata; `source-inputs/manifest.json` hashes every local input and lists additional archive origins. New raw context inputs larger than 8 MB were not introduced; the whole compressed source-input archive is approximately 6.3 MB. No second PBF scan, shell network access or binary download was performed by this shard.

`evidence.json` records per-feature source objects, URLs and limitations. `attempts.json` preserves all 66 searches and reviewed alternatives. `web-search-batch-*.json` retains connector research excerpts. `unresolved.json` has zero uncollected target names. `alias-proposals.json` has no unproven proposals. `summary.json` and `validation.json` record completion, WGS84 geometry validity, expected-name coverage, distinct geometries and frozen batch integrity.

`analyze.py`, `analysis.json`, `candidate-cells.geojson` and the preview images are diagnostic review artifacts. Candidate selection was manual. Source snapshot: 2026-11-12T21:23:05Z, PBF SHA-256 `224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a`. © OpenStreetMap contributors, ODbL-1.0. Municipal planning descriptions identify localities and parent/constituent relationships; they do not make inferred borders official.
