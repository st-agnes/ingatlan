# Budapest — 2026-11-15 remaining-name research

Importable output: `features.geojson`. The final packet contains **26 rough search-area polygons**, resolving all 26 names in the starting Budapest missing-name inventory. Every output explicitly sets `estimated: true`, `lowConfidence: true`, and records its method, sources, named boundary anchors and limitations. These are not official administrative boundaries. Historical and overlapping subdivisions are permitted and are not converted to aliases. Completing this name inventory does not prove exhaustive Budapest neighborhood coverage.

The geometry uses actual archived OSM street, railway and waterway fabric, together with public municipal, developer and historical descriptions. No point buffer, circle, rectangle generated from a point, Voronoi partition or parent-name substitution is used. For Európa lakókert and Nagyiccetelep, historical street-defined extents are retained even though the archived name points lie outside; these discrepancies are explicit in the features and summary. Kisszentmihály and Szent György-telep are source-bounded road/stream cells with a preserved native district edge. Their point only selects an existing cell and does not create its boundaries.

The 26 names are Budagyöngye, Csabaliget, Csillebérci Üdülőtelep, EcoLiget lakópark, Európa lakókert, Farkashegy, Felsőváros, Honfoglalás lakópark, Ilonatelep, Kakukkhegy, Királyhágó lakópark, Kisszentmihály, Malomdomb, Margit-negyed, Megyeri Hídfő, Nagyiccetelep, Nagyvásártelep, Palotai-sziget, Szabadságtelep, Szent György-telep, Szent László-telep, Szilasmenti TSz, Szárazhegy, Virágtelep, Óhegyi lakótelep and Újtelep.

Some footprints deliberately remain broad or partial estimates. EcoLiget follows the small private circulation envelope, rather than claiming to reproduce its entire cadastral parcel. Virágtelep uses a broad public-map street-group convention. Palotai-sziget is a historical riverfront locality estimate, not a certified copy of the protected nature-reserve parcel polygon. Megyeri Hídfő is a southern bridgehead estimate within the larger combined planning unit; it is not an alias for all Székesdűlő. Szárazhegy uses a broad locality ring and is not replaced by one Panoráma development phase.

`manual-traces.json` preserves all manual WGS84 vertices and their reasoning. `name-points.geojson`, `parent-features.geojson`, the four `*-source-roads.geojson.gz` archives, `context-*.png` and `context-registration.json` preserve the input evidence and map registration. Road archives retain complete selected OSM ways and their object URLs, timestamps, tags and original PBF SHA. `source-manifest.json` pins the preceding frozen archives from which this packet was extracted. `research/` and `research-estates/` preserve acquired web evidence and per-name research. OSM data: © OpenStreetMap contributors, ODbL-1.0; https://www.openstreetmap.org/copyright .

`preview-*.png`, `preview-contact-sheet.jpg` and `preview-registration.json` show each complete final ring over the preserved street fabric. Municipal PDFs centrally downloaded by the parent task are referenced in `downloaded-source-references.json` and kept under the sibling `../downloaded-sources/` folder; they are not duplicated here. No additional country PBF scan was run.

Run from the repository root with Python and Shapely installed:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python data/neighborhoods/expansion-20261115/budapest/build.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python data/neighborhoods/expansion-20261115/budapest/verify.py
```

The build is offline and deterministic. No country PBF is needed. Verification confirms all 26 nonempty valid Polygons, complete source metadata, no duplicate normalized names and byte-identical regeneration. `summary.json` records point containment without forcing boundaries to include questionable labels. `prepare-context.py` and `render-context.py` reproducibly recover the input subset/maps from the previous frozen Budapest packet; they are not needed to rebuild finished polygons. `render-previews.py` rebuilds the final ring previews.

`summary.json` reports zero remaining names in the starting inventory. Remaining source/label discrepancies and scope limits are recorded in `unresolved.json`; no aliases are proposed.
