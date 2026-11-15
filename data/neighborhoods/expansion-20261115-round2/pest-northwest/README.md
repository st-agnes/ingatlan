# Pest northwest — 2026-11-15 round 2

Frozen importable output: `features.geojson`, with 29 WGS84 polygons: Szentendre 8, Gödöllő 7, Budakeszi 7 and Piliscsaba 7. Every feature is explicitly `estimated: true`, `lowConfidence: true`; none establishes an official or surveyed perimeter. These cover the 29 missing names selected for those four municipalities at baseline commit `3f6e793`. The underlying name inventory is not an authoritative list of all neighborhoods, so complete city or national coverage is not established. Optional Pomáz 6 and Dabas 8 remain unresolved in this packet.

`manual-traces.json` stores each manual ring, named road/rail/waterway anchors and source-specific reasoning. The boundaries use the preserved actual source geometry and public place/street descriptions. They are not point circles, bounding boxes, Voronoi cells or one-building proxies. Rough joins and outer transitions are intentional estimates. `context-*.png` and `context-registration.json` preserve the actual street-map views used for tracing; red name points identify areas but do not generate their boundaries.

Historical and overlapping names remain separate. Szentendre's Füzespark polygon estimates the Vasvári Pál utca–Sas utca–Szentlászlói út triangle named in the municipal decree; it overlaps the separately identified smaller Vasvári estate. Skanzen estimates the museum-quarter campus rather than a museum building. Piliscsaba's Egyetem and Iosephinum are separate former northern/southern campus areas; Márialiget, Szállás and Ófalu have rough transitions. Gödöllő police service sectors support locality names and neighboring streets, rather than becoming whole child-neighborhood boundaries. Budakeszi's Hidegvölgy and Tiefenweg, and its József Attila and Honvéd estates, have not been merged. No aliases are proposed.

Inputs: `target-selection.json` freezes all 43 baseline missing names in the six considered towns; `prior-polygons.geojson` and `source-municipalities.geojson` freeze context. `cached-godollo-roads.geojson.gz` reuses the preceding frozen commuter-town packet. `cached-budakeszi-roads.geojson.gz` reuses saved Budapest-region source roads. `source-roads.geojson.gz` and `source-surfaces.geojson.gz` preserve complete OSM ways for the other towns from one local PBF scan. Sources retain original object URLs, tags, timestamps, PBF SHA and attribution. OSM data © OpenStreetMap contributors, ODbL-1.0: https://www.openstreetmap.org/copyright .

Acquired public web evidence and municipal PDF connector text are archived in `research/`. Each feature links the relevant public source. The referenced Szentendre and Piliscsaba PDF URLs were opened through the web connector; this packet does not claim those PDF files were downloaded or their boundary lines digitized. Road-map tracing and cited textual descriptions support the estimates. All acquired local source inputs are retained here and hashed by `source-manifest.json`.

Offline rebuild from repository root with Python and Shapely:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round2/pest-northwest/build.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round2/pest-northwest/verify.py
```

The completed build requires no network, country PBF or external downloads. `extract-context.py` is only a source reacquisition recipe, not part of rebuilding the frozen features. `append-piliscsaba.py`, `build-fuzes-trace.py` and municipality trace subsets document the assembly stages; `manual-traces.json` is the final build input. `validation.json` records valid geometry, per-name provenance, all 29 identification points inside the corresponding estimate, and byte-identical offline rebuild. These are integrity checks, not an accuracy audit. `summary.json` and `unresolved.json` retain the remaining optional names and limits.
